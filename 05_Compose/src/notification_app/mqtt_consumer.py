"""MQTT subscriber for Pair 04 (Core Business -> Notification).

Disabled by default (MQTT_ENABLED=false) so the container runs standalone
for Lab 04. Set MQTT_ENABLED=true to subscribe to the class broker
`mqtt://192.168.1.51:1883` (anonymous), topic `campus.alerts`.

Invalid payloads are not retried: they are forwarded to `campus.alerts.dlq`
together with the validation error (consumer rule Q04 in the event contract).
"""

from __future__ import annotations

from collections import deque
import concurrent.futures
from concurrent.futures import Future, ThreadPoolExecutor
import json
import logging
import threading
from typing import Deque, List, Optional, Set
from urllib.parse import urlparse

from pydantic import ValidationError

from .config import settings
from .models import event_adapter, iso_utc
from .store import store

logger = logging.getLogger("notification.mqtt")

DLQ_BUFFER_MAX = 50
_dlq_lock = threading.RLock()
_dlq_buffer: Deque[dict] = deque(maxlen=DLQ_BUFFER_MAX)


def _record_dlq_item(payload: dict) -> None:
    with _dlq_lock:
        _dlq_buffer.appendleft(dict(payload))


def get_dlq_items() -> List[dict]:
    with _dlq_lock:
        return [dict(item) for item in _dlq_buffer]


def dlq_count() -> int:
    with _dlq_lock:
        return len(_dlq_buffer)


def clear_dlq_buffer() -> None:
    with _dlq_lock:
        _dlq_buffer.clear()


def build_max_retries_dlq_payload(record: dict) -> dict:
    return {
        "topic": settings.mqtt_dlq_topic,
        "reason": "MAX_RETRIES_EXCEEDED",
        "error_detail": record.get("error_detail") or "Delivery failed after max retries",
        "retry_count": record.get("retry_count", 0),
        "failed_at": iso_utc(),
        "notification_id": record.get("notification_id"),
        "event_id": record.get("event_id"),
        "alert_id": record.get("alert_id"),
        "notification": dict(record),
    }


def record_dlq_from_store(record: dict) -> None:
    _record_dlq_item(build_max_retries_dlq_payload(record))


class MqttConsumer:
    def __init__(self, max_workers: Optional[int] = None) -> None:
        self._client = None
        self.connected = False
        self._max_workers = max_workers or settings.mqtt_worker_threads
        self._executor: Optional[ThreadPoolExecutor] = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="mqtt-worker",
        )
        self._futures_lock = threading.Lock()
        self._futures: Set[Future] = set()
        self._shutting_down = False

    def start(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:  # pragma: no cover
            logger.error("paho-mqtt is not installed; MQTT consumer disabled")
            return

        if self._executor is None or self._shutting_down:
            self._shutting_down = False
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="mqtt-worker",
            )

        url = urlparse(settings.mqtt_broker_url)
        host, port = url.hostname or "localhost", url.port or 1883

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.mqtt_client_id, clean_session=False)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client = client

        logger.info("connecting to MQTT broker %s:%s topic=%s", host, port, settings.mqtt_topic)
        client.connect_async(host, port, keepalive=30)
        client.loop_start()
        store.dlq_publisher = self.publish_dlq

    def stop(self) -> None:
        self._shutting_down = True
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
        if self._client is not None:
            if hasattr(self._client, "loop_stop"):
                self._client.loop_stop()
            if hasattr(self._client, "disconnect"):
                self._client.disconnect()
        self.connected = False
        if store.dlq_publisher == self.publish_dlq:
            store.dlq_publisher = None

    def wait_idle(self, timeout: Optional[float] = None) -> None:
        while True:
            with self._futures_lock:
                pending = list(self._futures)
            if not pending:
                return
            concurrent.futures.wait(pending, timeout=timeout)
            if timeout is not None:
                return

    # ---------------------------------------------------------------- callbacks
    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if getattr(reason_code, "is_failure", False):
            logger.error("MQTT connect failed: %s", reason_code)
            return
        self.connected = True
        client.subscribe(settings.mqtt_topic, qos=1)
        logger.info("MQTT connected, subscribed to %s (qos=1)", settings.mqtt_topic)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self.connected = False
        logger.warning("MQTT disconnected: %s (auto-reconnect enabled)", reason_code)

    def _discard_future(self, future: Future) -> None:
        with self._futures_lock:
            self._futures.discard(future)

    def _on_message(self, client, userdata, msg) -> Optional[Future]:
        raw = msg.payload.decode("utf-8", errors="replace")
        topic = getattr(msg, "topic", settings.mqtt_topic)
        if self._shutting_down or self._executor is None:
            logger.warning("ignoring MQTT message on %s while consumer is stopped", topic)
            return None
        future = self._executor.submit(self._process_message, topic, raw)
        with self._futures_lock:
            self._futures.add(future)
        future.add_done_callback(self._discard_future)
        return future

    def _process_message(self, topic: str, raw: str) -> None:
        parsed_data = None
        try:
            parsed_data = json.loads(raw)
            event = event_adapter.validate_python(parsed_data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("invalid event on %s -> DLQ: %s", topic, exc)
            dlq_payload: dict = {
                "topic": settings.mqtt_dlq_topic,
                "reason": "SCHEMA_VALIDATION_FAILED",
                "error_detail": str(exc)[:500],
                "retry_count": 0,
                "failed_at": iso_utc(),
                "source_topic": topic,
                "original_payload": raw[:4000],
            }
            if isinstance(parsed_data, dict):
                dlq_payload["event"] = parsed_data
            self._publish(settings.mqtt_dlq_topic, dlq_payload)
            return
        try:
            store.process(event, origin="mqtt")
        except Exception:  # pragma: no cover
            logger.exception("unhandled error processing MQTT event on %s", topic)

    # ---------------------------------------------------------------- publishing
    def publish_dlq(self, record: dict) -> None:
        self._publish(settings.mqtt_dlq_topic, build_max_retries_dlq_payload(record))

    def publish_raw(self, raw_text: str) -> None:
        if self._client is None:
            raise RuntimeError("MQTT client is not initialized")
        info = self._client.publish(settings.mqtt_topic, raw_text, qos=1)
        if info is not None and hasattr(info, "wait_for_publish"):
            try:
                info.wait_for_publish(timeout=2.0)
            except Exception as exc:
                raise RuntimeError(f"MQTT publish failed: {exc}") from exc

    def _publish(self, topic: str, body: dict) -> None:
        if topic == settings.mqtt_dlq_topic:
            _record_dlq_item(body)
        if self._client is None:
            return
        self._client.publish(topic, json.dumps(body, ensure_ascii=False), qos=1)


consumer: Optional[MqttConsumer] = None


def publish_raw(raw_text: str) -> None:
    if consumer is None:
        raise RuntimeError("MQTT consumer is not initialized")
    consumer.publish_raw(raw_text)


def start_consumer() -> Optional[MqttConsumer]:
    global consumer
    if not settings.mqtt_enabled:
        logger.info("MQTT consumer disabled (MQTT_ENABLED=false); REST fallback only")
        return None
    consumer = MqttConsumer()
    consumer.start()
    return consumer


def stop_consumer() -> None:
    if consumer is not None:
        consumer.stop()

