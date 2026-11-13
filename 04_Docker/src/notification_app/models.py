"""Pydantic v2 models mirroring contracts/notification.openapi.yaml.

The three event models are the same payloads Core Business publishes on
MQTT topic `campus.alerts` (event-contract-04-core-notification.md), so the
REST fallback and the async consumer share exactly one validation layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, List, Literal, Optional, Union
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, field_validator

ALERT_ID_PATTERN = r"^ALT-[0-9]{3,}$"


class SeverityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class NotificationChannel(str, Enum):
    telegram = "telegram"
    email = "email"
    discord = "discord"
    sms = "sms"


class DeliveryStatus(str, Enum):
    queued = "queued"
    delivered = "delivered"
    retrying = "retrying"
    failed = "failed"
    duplicate_ignored = "duplicate_ignored"


class _EventBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    correlationId: str = Field(min_length=1, max_length=100)
    source: Literal["core-business"]
    alert_id: str = Field(pattern=ALERT_ID_PATTERN)
    timestamp: AwareDatetime

    @field_validator("target_channels", check_fields=False)
    @classmethod
    def _unique_channels(cls, value: Optional[List[NotificationChannel]]):
        if value is not None and len(set(value)) != len(value):
            raise ValueError("target_channels must not contain duplicate channels")
        return value


class AlertCreatedEvent(_EventBase):
    event_name: Literal["alert.created"]
    severity: SeverityLevel
    message: str = Field(min_length=5, max_length=500)
    target_channels: Optional[List[NotificationChannel]] = Field(default=None, min_length=1, max_length=4)


class AlertEscalatedEvent(_EventBase):
    event_name: Literal["alert.escalated"]
    escalation_level: int = Field(ge=1, le=5)
    severity: Optional[SeverityLevel] = None
    message: Optional[str] = Field(default=None, min_length=5, max_length=500)
    target_channels: Optional[List[NotificationChannel]] = Field(default=None, min_length=1, max_length=4)


class AlertResolvedEvent(_EventBase):
    event_name: Literal["alert.resolved"]
    resolution_note: str = Field(min_length=3, max_length=500)
    target_channels: Optional[List[NotificationChannel]] = Field(default=None, min_length=1, max_length=4)


NotificationEventRequest = Annotated[
    Union[AlertCreatedEvent, AlertEscalatedEvent, AlertResolvedEvent],
    Field(discriminator="event_name"),
]

event_adapter: TypeAdapter = TypeAdapter(NotificationEventRequest)


class HealthStatus(BaseModel):
    status: Literal["ok"]
    service: str
    mqtt_broker: str
    subscribed_topic: str
    time: str


class NotificationLog(BaseModel):
    notification_id: str
    event_id: str
    event_name: Literal["alert.created", "alert.escalated", "alert.resolved"]
    correlationId: str
    source: str
    alert_id: str
    severity: Optional[SeverityLevel] = None
    message: Optional[str] = None
    channel: NotificationChannel
    target_channels: List[NotificationChannel]
    sent: bool
    status: DeliveryStatus
    retry_count: int = Field(ge=0)
    error_detail: Optional[str] = None
    created_at: str
    delivered_at: Optional[str] = None


class NotificationPage(BaseModel):
    items: List[NotificationLog]
    next_cursor: Optional[str] = None
    has_more: bool


class ProblemFieldError(BaseModel):
    field: str
    code: str
    message: str


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None
    errors: List[ProblemFieldError] = []


def iso_utc(value: Optional[datetime] = None) -> str:
    """Format a datetime as RFC 3339 UTC (`2026-08-27T15:30:00Z`)."""
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
