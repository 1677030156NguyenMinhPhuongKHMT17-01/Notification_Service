"""In-memory notification store + processing rules shared by REST and MQTT.

Rules implemented from event-contract-04-core-notification.md:
- Idempotency by `event_id` (duplicate -> 409 on REST, ignored on MQTT).
- Auto-routing of channels by `severity` when `target_channels` is omitted.
- Up to MAX_RETRIES automatic retries, RETRY_INTERVAL_SECONDS apart; after
  that the record is marked `failed` and handed to the DLQ publisher.
- Out-of-order tolerant: escalated/resolved events without a prior
  `alert.created` are still logged (severity/channels fall back to defaults).

Persistence (SQLite/PostgreSQL) is deferred to Lab 05 (Docker Compose).
"""

from __future__ import annotations

import base64
import binascii
import logging
import threading
import uuid
from typing import Callable, Dict, List, Optional, Tuple, Union

from .config import settings
from .delivery import deliver_all
from .models import AlertCreatedEvent, AlertEscalatedEvent, AlertResolvedEvent, iso_utc

logger = logging.getLogger("notification.store")

Event = Union[AlertCreatedEvent, AlertEscalatedEvent, AlertResolvedEvent]

SEVERITY_ROUTING: Dict[str, List[str]] = {
    "critical": ["telegram", "email", "sms"],
    "high": ["telegram", "email"],
    "medium": ["telegram"],
    "low": ["email"],
}


class InvalidCursor(ValueError):
    pass


class RetryLimitReached(RuntimeError):
    pass


class NotificationStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._logs: List[dict] = []
        self._by_id: Dict[str, dict] = {}
        self._by_event: Dict[str, dict] = {}
        self._timers: List[threading.Timer] = []
        self.dlq_publisher: Optional[Callable[[dict], None]] = None

    # ------------------------------------------------------------------ helpers
    def _latest_for_alert(self, alert_id: str) -> Optional[dict]:
        for item in reversed(self._logs):
            if item["alert_id"] == alert_id:
                return item
        return None

    def _derive(self, event: Event) -> Tuple[Optional[str], str, List[str]]:
        previous = self._latest_for_alert(event.alert_id)
        if isinstance(event, AlertCreatedEvent):
            severity = event.severity.value
            message = event.message
            channels = [c.value for c in event.target_channels] if event.target_channels else SEVERITY_ROUTING[severity]
        elif isinstance(event, AlertEscalatedEvent):
            base = (previous or {}).get("severity") or "high"
            severity = "critical" if event.escalation_level >= 3 else base
            message = f"Cảnh báo {event.alert_id} đã leo thang lên cấp {event.escalation_level}"
            if event.target_channels:
                channels = [c.value for c in event.target_channels]
            else:
                channels = SEVERITY_ROUTING[severity]
        else:
            severity = (previous or {}).get("severity")
            message = f"Cảnh báo {event.alert_id} đã được xử lý: {event.resolution_note}"
            channels = list((previous or {}).get("target_channels") or ["telegram"])
        return severity, message[:500], channels

    # --------------------------------------------------------------- processing
    def process(self, event: Event, origin: str) -> Tuple[dict, bool]:
        """Create a notification log for `event`. Returns (log, is_duplicate)."""
        event_id = str(event.event_id)
        with self._lock:
            existing = self._by_event.get(event_id)
            if existing is not None:
                logger.info("duplicate event_id=%s origin=%s ignored", event_id, origin)
                return existing, True

            severity, message, channels = self._derive(event)
            record = {
                "notification_id": str(uuid.uuid4()),
                "event_id": event_id,
                "event_name": event.event_name,
                "correlationId": event.correlationId,
                "source": event.source,
                "alert_id": event.alert_id,
                "severity": severity,
                "message": message,
                "channel": channels[0],
                "target_channels": channels,
                "sent": False,
                "status": "queued",
                "retry_count": 0,
                "error_detail": None,
                "created_at": iso_utc(),
                "delivered_at": None,
            }
            self._logs.append(record)
            self._by_id[record["notification_id"]] = record
            self._by_event[event_id] = record

        logger.info(
            "accepted event_name=%s event_id=%s alert_id=%s origin=%s channels=%s correlationId=%s",
            record["event_name"], event_id, record["alert_id"], origin, channels, record["correlationId"],
        )
        self._attempt(record)
        if record["status"] == "retrying":
            self._schedule_auto_retry(record["notification_id"])
        return dict(record), False

    def _attempt(self, record: dict) -> None:
        ok, errors = deliver_all(record["target_channels"], record["alert_id"], record["message"] or "", record["correlationId"])
        with self._lock:
            if ok:
                record.update(sent=True, status="delivered", error_detail=None, delivered_at=iso_utc())
            elif record["retry_count"] >= settings.max_retries:
                record.update(sent=False, status="failed", error_detail="; ".join(errors)[:500])
            else:
                record.update(sent=False, status="retrying", error_detail="; ".join(errors)[:500])

    def _schedule_auto_retry(self, notification_id: str) -> None:
        timer = threading.Timer(settings.retry_interval_seconds, self._auto_retry, args=(notification_id,))
        timer.daemon = True
        with self._lock:
            self._timers.append(timer)
        timer.start()

    def _auto_retry(self, notification_id: str) -> None:
        with self._lock:
            record = self._by_id.get(notification_id)
            if record is None or record["status"] != "retrying":
                return
            record["retry_count"] += 1
        logger.info("auto-retry notification_id=%s attempt=%s", notification_id, record["retry_count"])
        self._attempt(record)
        if record["status"] == "retrying":
            self._schedule_auto_retry(notification_id)
        elif record["status"] == "failed":
            self._send_to_dlq(record)

    def _send_to_dlq(self, record: dict) -> None:
        logger.error(
            "DLQ topic=%s notification_id=%s event_id=%s after %s retries: %s",
            settings.mqtt_dlq_topic, record["notification_id"], record["event_id"], record["retry_count"], record["error_detail"],
        )
        if self.dlq_publisher is not None:
            try:
                self.dlq_publisher(dict(record))
            except Exception:  # pragma: no cover - broker errors only logged
                logger.exception("failed to publish to DLQ")

    def manual_retry(self, notification_id: str) -> Optional[dict]:
        with self._lock:
            record = self._by_id.get(notification_id)
            if record is None:
                return None
            if record["retry_count"] >= settings.max_retries:
                raise RetryLimitReached(
                    f"Notification {notification_id} đã đạt tối đa {settings.max_retries} lần retry"
                )
            record["retry_count"] += 1
            record["status"] = "retrying"
        self._attempt(record)
        if record["status"] == "failed":
            self._send_to_dlq(record)
        return dict(record)

    # ------------------------------------------------------------------ queries
    def get(self, notification_id: str) -> Optional[dict]:
        with self._lock:
            record = self._by_id.get(notification_id)
            return dict(record) if record else None

    def page(
        self,
        limit: int,
        cursor: Optional[str] = None,
        alert_id: Optional[str] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> dict:
        offset = decode_cursor(cursor) if cursor else 0
        with self._lock:
            items = list(reversed(self._logs))
        if alert_id:
            items = [i for i in items if i["alert_id"] == alert_id]
        if status:
            items = [i for i in items if i["status"] == status]
        if channel:
            items = [i for i in items if channel in i["target_channels"]]
        window = items[offset : offset + limit]
        has_more = offset + limit < len(items)
        return {
            "items": [dict(i) for i in window],
            "next_cursor": encode_cursor(offset + limit) if has_more else None,
            "has_more": has_more,
        }

    def reset(self) -> None:
        with self._lock:
            for timer in self._timers:
                timer.cancel()
            self._timers.clear()
            self._logs.clear()
            self._by_id.clear()
            self._by_event.clear()


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        prefix, value = raw.split(":", 1)
        offset = int(value)
        if prefix != "o" or offset < 0:
            raise ValueError
        return offset
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise InvalidCursor("cursor không hợp lệ") from exc


store = NotificationStore()

