"""Runtime configuration for Notification Service.

Every value is read from environment variables so the same Docker image
can run on a laptop, in CI or on the class network without rebuilding.
No real secret is hard-coded here: `.env.example` only holds dev values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import FrozenSet


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_set(name: str) -> FrozenSet[str]:
    raw = os.getenv(name, "")
    return frozenset(item.strip().lower() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "notification-service"))
    service_version: str = field(default_factory=lambda: os.getenv("SERVICE_VERSION", "0.4.0"))
    env: str = field(default_factory=lambda: os.getenv("ENV", "local"))
    auth_token: str = field(default_factory=lambda: os.getenv("AUTH_TOKEN", "local-dev-token"))

    # Pair 04 – Core Business -> Notification (async, MQTT)
    mqtt_enabled: bool = field(default_factory=lambda: _env_bool("MQTT_ENABLED", False))
    mqtt_broker_url: str = field(default_factory=lambda: os.getenv("MQTT_BROKER_URL", "mqtt://192.168.1.51:1883"))
    mqtt_topic: str = field(default_factory=lambda: os.getenv("MQTT_TOPIC", "campus.alerts"))
    mqtt_dlq_topic: str = field(default_factory=lambda: os.getenv("MQTT_DLQ_TOPIC", "campus.alerts.dlq"))
    mqtt_client_id: str = field(default_factory=lambda: os.getenv("MQTT_CLIENT_ID", "notification-service-g7"))

    # Delivery policy (event-contract-04: max 3 retries, 5 s apart)
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    retry_interval_seconds: float = field(default_factory=lambda: float(os.getenv("RETRY_INTERVAL_SECONDS", "5")))

    # Lab/demo switch: channels listed here always fail, so the retry/DLQ path can be shown.
    fail_channels: FrozenSet[str] = field(default_factory=lambda: _env_set("FAIL_CHANNELS"))


settings = Settings()

