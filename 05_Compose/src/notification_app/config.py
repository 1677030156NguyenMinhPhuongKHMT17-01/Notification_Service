"""Runtime configuration for Notification Service (Lab 05 – Docker Compose)."""

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


def _resolve_database_url() -> str:
    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit:
        return explicit
    host = os.getenv("POSTGRES_HOST", "").strip()
    if not host:
        return ""
    user = os.getenv("POSTGRES_USER", "lab05")
    password = os.getenv("POSTGRES_PASSWORD", "lab05pass")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "notificationdb")
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


@dataclass(frozen=True)
class Settings:
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "notification-service"))
    service_version: str = field(default_factory=lambda: os.getenv("SERVICE_VERSION", "0.5.0"))
    env: str = field(default_factory=lambda: os.getenv("ENV", "local"))
    auth_token: str = field(default_factory=lambda: os.getenv("AUTH_TOKEN", "local-dev-token"))

    # PostgreSQL persistence (empty -> in-memory fallback for unit tests)
    database_url: str = field(default_factory=_resolve_database_url)

    # Pair 04 – Core Business -> Notification (async, MQTT)
    mqtt_enabled: bool = field(default_factory=lambda: _env_bool("MQTT_ENABLED", True))
    mqtt_broker_url: str = field(default_factory=lambda: os.getenv("MQTT_BROKER_URL", "mqtt://mqtt-broker:1883"))
    mqtt_topic: str = field(default_factory=lambda: os.getenv("MQTT_TOPIC", "campus.alerts"))
    mqtt_dlq_topic: str = field(default_factory=lambda: os.getenv("MQTT_DLQ_TOPIC", "campus.alerts.dlq"))
    mqtt_client_id: str = field(default_factory=lambda: os.getenv("MQTT_CLIENT_ID", "notification-service-g6"))
    mqtt_worker_threads: int = field(default_factory=lambda: max(1, int(os.getenv("MQTT_WORKER_THREADS", "4"))))

    # Delivery policy (event-contract-04: max 3 retries, 5 s apart)
    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    retry_interval_seconds: float = field(default_factory=lambda: float(os.getenv("RETRY_INTERVAL_SECONDS", "5")))
    fail_channels: FrozenSet[str] = field(default_factory=lambda: _env_set("FAIL_CHANNELS"))

    # Optional real channel adapters (stdlib urllib, <=5s timeout; stdout mock when unset)
    discord_webhook_url: str = field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", "").strip())
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "").strip())
    webhook_timeout_seconds: float = field(
        default_factory=lambda: max(0.1, min(float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "5")), 5.0))
    )


settings = Settings()

