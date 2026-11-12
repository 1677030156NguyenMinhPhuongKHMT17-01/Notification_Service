"""MQTT subscriber for Pair 04 (Core Business -> Notification).

Disabled by default (MQTT_ENABLED=false) so the container runs standalone
for Lab 04. Set MQTT_ENABLED=true to subscribe to the class broker
`mqtt://192.168.1.51:1883` (anonymous), topic `campus.alerts`.

Invalid payloads are not retried: they are forwarded to `campus.alerts.dlq`
together with the validation error (consumer rule Q04 in the event contract).
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.parse import urlparse

from pydantic import ValidationError

from .config import settings
from .models import event_adapter, iso_utc
from .store import store

logger = logging.getLogger("notification.mqtt")


class MqttConsumer:
    def __init__(self) -> None:
        self._client = None
        self.connected = False

    def start(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:  # pragma: no cover
            logger.error("paho-mqtt is not installed; MQTT consumer disabled")
            return

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
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()

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

    def _on_message(self, client, userdata, msg) -> None:
        raw = msg.payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
            event = event_adapter.validate_python(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("invalid event on %s -> DLQ: %s", msg.topic, exc)
            self._publish(settings.mqtt_dlq_topic, {
                "reason": "schema_validation_failed",
                "error": str(exc)[:500],
                "original_payload": raw[:4000],
                "received_at": iso_utc(),
            })
            return
        store.process(event, origin="mqtt")

    # ---------------------------------------------------------------- publishing
    def publish_dlq(self, record: dict) -> None:
        self._publish(settings.mqtt_dlq_topic, {"reason": "max_retries_exceeded", "notification": record, "received_at": iso_utc()})

    def _publish(self, topic: str, body: dict) -> None:
        if self._client is None:
            return
        self._client.publish(topic, json.dumps(body, ensure_ascii=False), qos=1)


consumer: Optional[MqttConsumer] = None


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

