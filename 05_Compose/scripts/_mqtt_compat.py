"""Lightweight MQTT publish/subscribe helper for Lab 05/06 CLI scripts.

Uses `paho-mqtt` when installed, and transparently falls back to a minimal
Python stdlib MQTT 3.1.1 TCP client so demo/DLQ scripts also run out-of-the-box
on a clean host Python without third-party packages.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Callable, Optional, Tuple
from urllib.parse import urlparse


def parse_broker_url(broker_url: str) -> Tuple[str, int]:
    normalized = broker_url.strip()
    if "://" not in normalized:
        normalized = f"mqtt://{normalized}"
    parsed = urlparse(normalized)
    return parsed.hostname or "127.0.0.1", parsed.port or 1883


def _encode_remaining_length(length: int) -> bytes:
    out = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length > 0:
            digit |= 0x80
        out.append(digit)
        if length == 0:
            break
    return bytes(out)


def _encode_str(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("!H", len(raw)) + raw


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    buf = bytearray()
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise ConnectionError("MQTT broker closed connection")
        buf.extend(chunk)
    return bytes(buf)


def _read_packet(sock: socket.socket) -> Tuple[int, bytes]:
    header = _recv_exact(sock, 1)[0]
    multiplier = 1
    remaining = 0
    while True:
        encoded = _recv_exact(sock, 1)[0]
        remaining += (encoded & 0x7F) * multiplier
        if (encoded & 0x80) == 0:
            break
        multiplier *= 128
    payload = _recv_exact(sock, remaining) if remaining else b""
    return header, payload


def _connect_stdlib(host: str, port: int, client_id: str, timeout: float = 5.0) -> socket.socket:
    sock = socket.create_connection((host, port), timeout=timeout)
    var_header = _encode_str("MQTT") + bytes([0x04, 0x02]) + struct.pack("!H", 60)
    body = var_header + _encode_str(client_id)
    sock.sendall(b"\x10" + _encode_remaining_length(len(body)) + body)
    header, payload = _read_packet(sock)
    if (header & 0xF0) != 0x20 or len(payload) < 2 or payload[1] != 0:
        sock.close()
        code = payload[1] if len(payload) >= 2 else -1
        raise ConnectionError(f"MQTT CONNACK rejected with code={code}")
    return sock


def publish_once(
    broker_url: str,
    topic: str,
    payload: str,
    client_id: str,
    qos: int = 1,
    timeout: float = 5.0,
) -> None:
    host, port = parse_broker_url(broker_url)
    try:
        import paho.mqtt.client as mqtt

        connected = threading.Event()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        client.on_connect = lambda *_args: connected.set()
        client.connect(host, port, keepalive=30)
        client.loop_start()
        try:
            if not connected.wait(timeout=timeout):
                raise TimeoutError(f"Timed out connecting to MQTT broker {host}:{port}")
            info = client.publish(topic, payload, qos=qos)
            info.wait_for_publish(timeout=timeout)
        finally:
            client.loop_stop()
            client.disconnect()
        return
    except ImportError:
        pass

    sock = _connect_stdlib(host, port, client_id, timeout=timeout)
    try:
        pkt_id = 1
        var_header = _encode_str(topic) + (struct.pack("!H", pkt_id) if qos > 0 else b"")
        body = var_header + payload.encode("utf-8")
        first_byte = 0x30 | ((qos & 0x03) << 1)
        sock.sendall(bytes([first_byte]) + _encode_remaining_length(len(body)) + body)
        if qos == 1:
            header, ack_payload = _read_packet(sock)
            if (header & 0xF0) != 0x40 or len(ack_payload) < 2:
                raise ConnectionError("Expected MQTT PUBACK from broker")
        sock.sendall(b"\xe0\x00")
    finally:
        sock.close()


def subscribe_loop(
    broker_url: str,
    topic: str,
    client_id: str,
    on_message: Callable[[str, str], None],
    max_messages: int = 0,
    timeout: float = 0.0,
) -> int:
    host, port = parse_broker_url(broker_url)
    try:
        import paho.mqtt.client as mqtt

        received = 0
        done = threading.Event()

        def _on_connect(client, _userdata, _flags, reason_code, _properties=None):
            if getattr(reason_code, "is_failure", False):
                done.set()
                return
            client.subscribe(topic, qos=1)

        def _on_msg(_client, _userdata, msg):
            nonlocal received
            raw = msg.payload.decode("utf-8", errors="replace")
            on_message(msg.topic, raw)
            received += 1
            if max_messages > 0 and received >= max_messages:
                done.set()

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        client.on_connect = _on_connect
        client.on_message = _on_msg
        client.connect(host, port, keepalive=30)
        client.loop_start()
        try:
            deadline: Optional[float] = (time.monotonic() + timeout) if timeout > 0 else None
            while not done.is_set():
                remaining = 0.25 if deadline is None else max(0.0, min(0.25, deadline - time.monotonic()))
                if deadline is not None and time.monotonic() >= deadline:
                    break
                done.wait(timeout=remaining)
        except KeyboardInterrupt:
            pass
        finally:
            client.loop_stop()
            client.disconnect()
        return received
    except ImportError:
        pass

    sock = _connect_stdlib(host, port, client_id)
    received = 0
    try:
        sub_body = struct.pack("!H", 1) + _encode_str(topic) + b"\x01"
        sock.sendall(b"\x82" + _encode_remaining_length(len(sub_body)) + sub_body)
        header, _ = _read_packet(sock)
        if (header & 0xF0) != 0x90:
            raise ConnectionError("Expected MQTT SUBACK from broker")

        deadline = (time.monotonic() + timeout) if timeout > 0 else None
        last_ping = time.monotonic()
        while True:
            if max_messages > 0 and received >= max_messages:
                break
            if deadline is not None and time.monotonic() >= deadline:
                break
            sock.settimeout(0.5)
            try:
                pkt_header, pkt_payload = _read_packet(sock)
            except socket.timeout:
                if time.monotonic() - last_ping >= 25.0:
                    sock.sendall(b"\xc0\x00")
                    last_ping = time.monotonic()
                continue

            pkt_type = pkt_header & 0xF0
            if pkt_type == 0x30:
                qos = (pkt_header >> 1) & 0x03
                tlen = struct.unpack("!H", pkt_payload[:2])[0]
                msg_topic = pkt_payload[2 : 2 + tlen].decode("utf-8", errors="replace")
                idx = 2 + tlen
                if qos > 0:
                    pkt_id = struct.unpack("!H", pkt_payload[idx : idx + 2])[0]
                    idx += 2
                    if qos == 1:
                        sock.sendall(b"\x40\x02" + struct.pack("!H", pkt_id))
                msg_text = pkt_payload[idx:].decode("utf-8", errors="replace")
                on_message(msg_topic, msg_text)
                received += 1
        sock.sendall(b"\xe0\x00")
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
    return received
