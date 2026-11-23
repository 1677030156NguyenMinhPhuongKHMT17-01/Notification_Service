"""Interactive Demo UI & operational observability endpoints (excluded from OpenAPI schema)."""

from __future__ import annotations

import json
import math
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Body, Depends, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from . import delivery, mqtt_consumer
from .config import settings
from .models import ALERT_ID_PATTERN, iso_utc
from .store import SEVERITY_ROUTING, _UNSET, store

STATIC_DIR = Path(__file__).resolve().parent / "static"

VALID_CHANNELS = frozenset({"telegram", "email", "discord", "sms"})
DEV_TOKEN_ENVS = frozenset({"local", "plugathon"})
DEV_SAFE_TOKENS = frozenset({"plugathon-dev-token", "local-dev-token"})

demo_router = APIRouter(include_in_schema=False)


def _verify_bearer(authorization: Optional[str] = Header(default=None)) -> None:
    from .main import verify_bearer_token

    verify_bearer_token(authorization)


def _problem(status_code: int, slug: str, title: str, detail: str) -> Exception:
    from .main import ProblemException

    return ProblemException(status_code, slug, title, detail)


class FaultUpdateRequest(BaseModel):
    fail_channels: Optional[List[str]] = None
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    retry_interval_seconds: Optional[float] = Field(default=None, ge=0.1, le=30.0)

    @field_validator("fail_channels")
    @classmethod
    def _validate_channels(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        cleaned: List[str] = []
        for channel in value:
            if not isinstance(channel, str) or channel not in VALID_CHANNELS:
                raise ValueError(f"Channel '{channel}' không hợp lệ; phải thuộc {sorted(VALID_CHANNELS)}")
            if channel not in cleaned:
                cleaned.append(channel)
        return cleaned

    @field_validator("max_retries", mode="before")
    @classmethod
    def _reject_bool_retries(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("max_retries phải là số nguyên từ 0 đến 10")
        return value

    @field_validator("retry_interval_seconds")
    @classmethod
    def _validate_interval(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not math.isfinite(value):
            raise ValueError("retry_interval_seconds phải là số hữu hạn")
        return value


class MqttPublishRequest(BaseModel):
    scenario: Optional[Literal["lifecycle", "duplicate_q05", "out_of_order_q09", "invalid_schema_dlq"]] = None
    alert_id: Optional[str] = Field(default=None, pattern=ALERT_ID_PATTERN)
    payload: Optional[Dict[str, Any]] = None
    raw_payload: Optional[str] = None

    @model_validator(mode="after")
    def _require_input(self) -> "MqttPublishRequest":
        has_raw = self.raw_payload is not None and self.raw_payload.strip() != ""
        if self.scenario is None and self.payload is None and not has_raw:
            raise ValueError("Cần cung cấp ít nhất một trong các trường: scenario, payload hoặc raw_payload")
        return self


@demo_router.get("/", include_in_schema=False)
@demo_router.get("/demo", include_in_schema=False)
def serve_demo_ui() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise _problem(404, "not-found", "Không tìm thấy giao diện Demo", "Tệp static/index.html chưa tồn tại")
    return FileResponse(index_path, media_type="text/html; charset=utf-8")


@demo_router.get("/demo-api/config", include_in_schema=False)
def get_demo_config() -> dict:
    dev_token_hint = (
        settings.auth_token
        if settings.env in DEV_TOKEN_ENVS and settings.auth_token in DEV_SAFE_TOKENS
        else None
    )
    return {
        "service_name": settings.service_name,
        "service_version": settings.service_version,
        "env": settings.env,
        "backend": store.backend_name,
        "mqtt_enabled": settings.mqtt_enabled,
        "mqtt_broker": settings.mqtt_broker_url,
        "mqtt_topic": settings.mqtt_topic,
        "mqtt_dlq_topic": settings.mqtt_dlq_topic,
        "mqtt_client_id": settings.mqtt_client_id,
        "default_max_retries": settings.max_retries,
        "default_retry_interval_seconds": settings.retry_interval_seconds,
        "severity_routing": {k: list(v) for k, v in SEVERITY_ROUTING.items()},
        "webhook_modes": {ch: delivery.channel_mode(ch) for ch in ("telegram", "discord", "email", "sms")},
        "dev_token_hint": dev_token_hint,
    }


@demo_router.get("/demo-api/overview", dependencies=[Depends(_verify_bearer)], include_in_schema=False)
def get_demo_overview() -> dict:
    return store.overview()


@demo_router.get("/demo-api/dlq", dependencies=[Depends(_verify_bearer)], include_in_schema=False)
def get_demo_dlq() -> dict:
    items = mqtt_consumer.get_dlq_items()
    return {
        "topic": settings.mqtt_dlq_topic,
        "count": len(items),
        "items": items,
    }


@demo_router.get("/demo-api/delivery-feed", dependencies=[Depends(_verify_bearer)], include_in_schema=False)
def get_demo_delivery_feed() -> dict:
    items = delivery.get_delivery_feed()
    return {
        "count": len(items),
        "items": items,
    }


@demo_router.get("/demo-api/faults", dependencies=[Depends(_verify_bearer)], include_in_schema=False)
def get_demo_faults() -> dict:
    return store.active_faults()


@demo_router.post("/demo-api/faults", dependencies=[Depends(_verify_bearer)], include_in_schema=False)
def update_demo_faults(payload: FaultUpdateRequest = Body(...)) -> dict:
    fields = payload.model_fields_set
    return store.configure_faults(
        fail_channels=payload.fail_channels if "fail_channels" in fields else _UNSET,
        max_retries=payload.max_retries if "max_retries" in fields else _UNSET,
        retry_interval_seconds=payload.retry_interval_seconds if "retry_interval_seconds" in fields else _UNSET,
    )


@demo_router.post("/demo-api/faults/reset", dependencies=[Depends(_verify_bearer)], include_in_schema=False)
def reset_demo_faults() -> dict:
    return store.reset_faults()


def _build_scenario_events(scenario: str, alert_id: str) -> List[Tuple[dict, float]]:
    now = datetime.now(timezone.utc)
    corr_id = f"req-demo-{uuid.uuid4().hex[:8]}"

    if scenario == "lifecycle":
        created = {
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.created",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": alert_id,
            "severity": "high",
            "message": f"[Demo UI] Sự cố mức high tại {alert_id} (auto-routing discord)",
            "timestamp": iso_utc(now - timedelta(seconds=20)),
        }
        escalated = {
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": alert_id,
            "escalation_level": 3,
            "severity": "critical",
            "message": f"[Demo UI] Cảnh báo {alert_id} leo thang cấp 3",
            "timestamp": iso_utc(now - timedelta(seconds=10)),
        }
        resolved = {
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.resolved",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": alert_id,
            "resolution_note": "Đội trực Demo UI xác nhận đã xử lý sự cố.",
            "target_channels": ["email", "discord"],
            "timestamp": iso_utc(now),
        }
        return [(created, 0.15), (escalated, 0.15), (resolved, 0.0)]

    if scenario == "duplicate_q05":
        dup_event = {
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.created",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": alert_id,
            "severity": "medium",
            "message": f"[Demo UI Q05] Sự kiện kiểm tra idempotency trùng event_id cho {alert_id}",
            "timestamp": iso_utc(now),
        }
        return [(dup_event, 0.15), (dict(dup_event), 0.0)]

    if scenario == "out_of_order_q09":
        resolved_first = {
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.resolved",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": alert_id,
            "resolution_note": "Q09 demo: sự cố đã đóng trước khi event tạo trễ tới broker.",
            "target_channels": ["email"],
            "timestamp": iso_utc(now),
        }
        late_created = {
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.created",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": alert_id,
            "severity": "critical",
            "message": f"[Demo UI Q09] Sự kiện alert.created đến trễ cho {alert_id}",
            "timestamp": iso_utc(now - timedelta(minutes=5)),
        }
        return [(resolved_first, 0.3), (late_created, 0.0)]

    invalid_event = {
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.deleted",
        "correlationId": corr_id,
        "source": "core-business",
        "alert_id": alert_id,
        "severity": "EXTREME",
        "timestamp": iso_utc(now),
    }
    return [(invalid_event, 0.0)]


@demo_router.post("/demo-api/mqtt/publish", dependencies=[Depends(_verify_bearer)], include_in_schema=False)
def publish_demo_mqtt(body: MqttPublishRequest = Body(...)) -> dict:
    consumer = mqtt_consumer.consumer
    if not settings.mqtt_enabled or consumer is None or not consumer.connected:
        raise _problem(
            503,
            "service-unavailable",
            "MQTT Consumer chưa sẵn sàng",
            "MQTT đang tắt (MQTT_ENABLED=false) hoặc chưa kết nối tới MQTT Broker.",
        )

    alert_id = body.alert_id or f"ALT-{random.randint(600, 999)}"
    published_events: List[dict] = []

    try:
        if body.scenario is not None:
            for event_obj, delay_sec in _build_scenario_events(body.scenario, alert_id):
                consumer.publish_raw(json.dumps(event_obj, ensure_ascii=False))
                published_events.append(
                    {
                        "event_name": event_obj.get("event_name"),
                        "event_id": event_obj.get("event_id"),
                        "alert_id": event_obj.get("alert_id"),
                        "correlationId": event_obj.get("correlationId"),
                        "payload": event_obj,
                    }
                )
                if delay_sec > 0:
                    time.sleep(delay_sec)
        elif body.payload is not None:
            consumer.publish_raw(json.dumps(body.payload, ensure_ascii=False))
            published_events.append(
                {
                    "event_name": body.payload.get("event_name"),
                    "event_id": body.payload.get("event_id"),
                    "alert_id": body.payload.get("alert_id"),
                    "correlationId": body.payload.get("correlationId"),
                    "payload": body.payload,
                }
            )
        else:
            raw_text = body.raw_payload or ""
            consumer.publish_raw(raw_text)
            parsed: Any = raw_text
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                pass
            parsed_dict = parsed if isinstance(parsed, dict) else {}
            published_events.append(
                {
                    "event_name": parsed_dict.get("event_name"),
                    "event_id": parsed_dict.get("event_id"),
                    "alert_id": parsed_dict.get("alert_id"),
                    "correlationId": parsed_dict.get("correlationId"),
                    "payload": parsed,
                }
            )
    except RuntimeError as exc:
        raise _problem(503, "service-unavailable", "Không thể publish sự kiện MQTT", str(exc)) from exc

    return {
        "broker": settings.mqtt_broker_url,
        "topic": settings.mqtt_topic,
        "published_count": len(published_events),
        "events": published_events,
        "time": iso_utc(),
    }
