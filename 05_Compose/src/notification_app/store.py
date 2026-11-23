"""Notification persistence and processing rules (PostgreSQL + in-memory fallback).

Business rules (from event-contract-04-core-notification.md) live once inside
`NotificationStore`, delegating persistence cleanly to either `PostgresBackend`
(used in Docker Compose) or `MemoryBackend` (used when `DATABASE_URL` is unset,
such as isolated unit tests).
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Dict, FrozenSet, Iterable, Iterator, List, Optional, Tuple, Union

from .config import settings
from . import delivery as delivery_mod
from .delivery import deliver_all
from .models import AlertCreatedEvent, AlertEscalatedEvent, AlertResolvedEvent, iso_utc

_UNSET = object()

logger = logging.getLogger("notification.store")

Event = Union[AlertCreatedEvent, AlertEscalatedEvent, AlertResolvedEvent]

SEVERITY_ROUTING: Dict[str, List[str]] = {
    "low": ["email"],
    "medium": ["telegram", "email"],
    "high": ["telegram", "email", "discord"],
    "critical": ["telegram", "email", "discord", "sms"],
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notifications (
    seq BIGSERIAL PRIMARY KEY,
    notification_id TEXT NOT NULL UNIQUE,
    event_id TEXT NOT NULL UNIQUE,
    event_name TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    source TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    severity TEXT,
    message TEXT,
    channel TEXT NOT NULL,
    target_channels JSONB NOT NULL,
    sent BOOLEAN NOT NULL,
    status TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_detail TEXT,
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    event_timestamp TEXT
);
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS event_timestamp TEXT;
CREATE INDEX IF NOT EXISTS idx_notifications_alert_id ON notifications (alert_id);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications (status);
"""


def _parse_iso_utc(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class InvalidCursor(ValueError):
    pass


class RetryLimitReached(RuntimeError):
    pass


class MemoryBackend:
    backend_name = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._logs: List[dict] = []
        self._by_id: Dict[str, dict] = {}
        self._by_event: Dict[str, dict] = {}
        self._resolved_at: Dict[str, datetime] = {}

    def init(self) -> None:
        return None

    def ping(self) -> bool:
        return True

    def get_by_id(self, notification_id: str) -> Optional[dict]:
        with self._lock:
            row = self._by_id.get(notification_id)
            return dict(row) if row else None

    def get_by_event_id(self, event_id: str) -> Optional[dict]:
        with self._lock:
            row = self._by_event.get(event_id)
            return dict(row) if row else None

    def latest_for_alert(self, alert_id: str) -> Optional[dict]:
        with self._lock:
            for item in reversed(self._logs):
                if item["alert_id"] == alert_id:
                    return dict(item)
        return None

    def latest_resolved_timestamp(self, alert_id: str) -> Optional[datetime]:
        with self._lock:
            return self._resolved_at.get(alert_id)

    def insert(self, record: dict) -> None:
        with self._lock:
            event_ts = record.get("event_timestamp")
            stored = {k: v for k, v in record.items() if k != "event_timestamp"}
            self._logs.append(stored)
            self._by_id[stored["notification_id"]] = stored
            self._by_event[stored["event_id"]] = stored
            if stored["event_name"] == "alert.resolved" and event_ts:
                parsed = _parse_iso_utc(event_ts)
                prev = self._resolved_at.get(stored["alert_id"])
                if prev is None or parsed > prev:
                    self._resolved_at[stored["alert_id"]] = parsed

    def update(self, record: dict) -> None:
        with self._lock:
            target = self._by_id.get(record["notification_id"])
            if target is not None:
                for key, value in record.items():
                    if key != "event_timestamp":
                        target[key] = value

    def recover_stuck_retrying(self) -> int:
        recovered = 0
        suffix = "Retry interrupted by service restart"
        with self._lock:
            for item in self._logs:
                if item["status"] == "retrying":
                    item["sent"] = False
                    item["status"] = "failed"
                    detail = item.get("error_detail") or ""
                    if not detail:
                        item["error_detail"] = suffix
                    elif suffix not in detail:
                        item["error_detail"] = f"{detail}; {suffix}"[:500]
                    recovered += 1
        return recovered

    def query_page(
        self,
        limit: int,
        offset: int,
        alert_id: Optional[str] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Tuple[List[dict], bool]:
        with self._lock:
            items = list(reversed(self._logs))
        if alert_id:
            items = [i for i in items if i["alert_id"] == alert_id]
        if status:
            items = [i for i in items if i["status"] == status]
        if channel:
            items = [i for i in items if channel in i["target_channels"]]
        window = items[offset : offset + limit]
        return [dict(i) for i in window], offset + limit < len(items)

    def clear(self) -> None:
        with self._lock:
            self._logs.clear()
            self._by_id.clear()
            self._by_event.clear()
            self._resolved_at.clear()

    def aggregate(self) -> dict:
        by_status = {"delivered": 0, "retrying": 0, "failed": 0, "duplicate_ignored": 0, "queued": 0}
        by_event_name = {"alert.created": 0, "alert.escalated": 0, "alert.resolved": 0}
        by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0, "none": 0}
        by_channel = {"telegram": 0, "email": 0, "discord": 0, "sms": 0}
        with self._lock:
            total = len(self._logs)
            for item in self._logs:
                status = item.get("status")
                if status in by_status:
                    by_status[status] += 1
                event_name = item.get("event_name")
                if event_name in by_event_name:
                    by_event_name[event_name] += 1
                severity = item.get("severity") or "none"
                if severity in by_severity:
                    by_severity[severity] += 1
                else:
                    by_severity["none"] += 1
                for channel in item.get("target_channels") or []:
                    if channel in by_channel:
                        by_channel[channel] += 1
        return {
            "total": total,
            "by_status": by_status,
            "by_event_name": by_event_name,
            "by_severity": by_severity,
            "by_channel": by_channel,
        }


class PostgresBackend:
    backend_name = "postgresql"

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @contextmanager
    def _conn(self) -> Iterator:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self._dsn, row_factory=dict_row, connect_timeout=3) as conn:
            yield conn

    @staticmethod
    def _to_record(row: Optional[dict]) -> Optional[dict]:
        if row is None:
            return None
        channels = row["target_channels"]
        if isinstance(channels, str):
            channels = json.loads(channels)
        return {
            "notification_id": row["notification_id"],
            "event_id": row["event_id"],
            "event_name": row["event_name"],
            "correlationId": row["correlation_id"],
            "source": row["source"],
            "alert_id": row["alert_id"],
            "severity": row["severity"],
            "message": row["message"],
            "channel": row["channel"],
            "target_channels": channels,
            "sent": row["sent"],
            "status": row["status"],
            "retry_count": row["retry_count"],
            "error_detail": row["error_detail"],
            "created_at": row["created_at"],
            "delivered_at": row["delivered_at"],
        }

    def init(self) -> None:
        with self._conn() as conn:
            conn.execute(SCHEMA_SQL)
            conn.commit()
        logger.info("PostgreSQL schema ready")

    def ping(self) -> bool:
        try:
            with self._conn() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception as exc:
            logger.warning("PostgreSQL ping failed: %s", exc)
            return False

    def get_by_id(self, notification_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM notifications WHERE notification_id = %s",
                (notification_id,),
            ).fetchone()
        return self._to_record(row)

    def get_by_event_id(self, event_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM notifications WHERE event_id = %s",
                (event_id,),
            ).fetchone()
        return self._to_record(row)

    def latest_for_alert(self, alert_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM notifications WHERE alert_id = %s ORDER BY seq DESC LIMIT 1",
                (alert_id,),
            ).fetchone()
        return self._to_record(row)

    def latest_resolved_timestamp(self, alert_id: str) -> Optional[datetime]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT event_timestamp FROM notifications "
                "WHERE alert_id = %s AND event_name = 'alert.resolved' AND event_timestamp IS NOT NULL",
                (alert_id,),
            ).fetchall()
        timestamps = [_parse_iso_utc(r["event_timestamp"]) for r in rows if r.get("event_timestamp")]
        return max(timestamps) if timestamps else None

    def insert(self, record: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO notifications (
                    notification_id, event_id, event_name, correlation_id, source,
                    alert_id, severity, message, channel, target_channels,
                    sent, status, retry_count, error_detail, created_at, delivered_at,
                    event_timestamp
                ) VALUES (
                    %(notification_id)s, %(event_id)s, %(event_name)s, %(correlationId)s, %(source)s,
                    %(alert_id)s, %(severity)s, %(message)s, %(channel)s, %(target_channels)s::jsonb,
                    %(sent)s, %(status)s, %(retry_count)s, %(error_detail)s, %(created_at)s, %(delivered_at)s,
                    %(event_timestamp)s
                )
                """,
                {
                    **record,
                    "target_channels": json.dumps(record["target_channels"]),
                    "event_timestamp": record.get("event_timestamp"),
                },
            )
            conn.commit()

    def update(self, record: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE notifications
                SET sent = %(sent)s,
                    status = %(status)s,
                    retry_count = %(retry_count)s,
                    error_detail = %(error_detail)s,
                    delivered_at = %(delivered_at)s
                WHERE notification_id = %(notification_id)s
                """,
                record,
            )
            conn.commit()

    def recover_stuck_retrying(self) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE notifications
                SET sent = FALSE,
                    status = 'failed',
                    error_detail = CASE
                        WHEN error_detail IS NULL OR error_detail = '' THEN 'Retry interrupted by service restart'
                        WHEN POSITION('Retry interrupted by service restart' IN error_detail) > 0 THEN error_detail
                        ELSE LEFT(error_detail || '; Retry interrupted by service restart', 500)
                    END
                WHERE status = 'retrying'
                """
            )
            conn.commit()
            return getattr(cur, "rowcount", 0) or 0

    def query_page(
        self,
        limit: int,
        offset: int,
        alert_id: Optional[str] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Tuple[List[dict], bool]:
        clauses: List[str] = []
        params: List[object] = []
        if alert_id:
            clauses.append("alert_id = %s")
            params.append(alert_id)
        if status:
            clauses.append("status = %s")
            params.append(status)
        if channel:
            clauses.append("target_channels ? %s")
            params.append(channel)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM notifications {where_sql} ORDER BY seq DESC LIMIT %s OFFSET %s"
        params.extend([limit + 1, offset])

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        has_more = len(rows) > limit
        records = [self._to_record(r) for r in rows[:limit]]
        return [r for r in records if r is not None], has_more

    def clear(self) -> None:
        with self._conn() as conn:
            conn.execute("TRUNCATE TABLE notifications RESTART IDENTITY")
            conn.commit()

    def aggregate(self) -> dict:
        by_status = {"delivered": 0, "retrying": 0, "failed": 0, "duplicate_ignored": 0, "queued": 0}
        by_event_name = {"alert.created": 0, "alert.escalated": 0, "alert.resolved": 0}
        by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0, "none": 0}
        by_channel = {"telegram": 0, "email": 0, "discord": 0, "sms": 0}
        with self._conn() as conn:
            total_row = conn.execute("SELECT COUNT(*) AS cnt FROM notifications").fetchone()
            total = int((total_row or {}).get("cnt") or 0)

            for row in conn.execute("SELECT status AS key, COUNT(*) AS cnt FROM notifications GROUP BY status").fetchall():
                key = row.get("key")
                if key in by_status:
                    by_status[key] = int(row.get("cnt") or 0)

            for row in conn.execute(
                "SELECT event_name AS key, COUNT(*) AS cnt FROM notifications GROUP BY event_name"
            ).fetchall():
                key = row.get("key")
                if key in by_event_name:
                    by_event_name[key] = int(row.get("cnt") or 0)

            for row in conn.execute(
                "SELECT COALESCE(NULLIF(severity, ''), 'none') AS key, COUNT(*) AS cnt "
                "FROM notifications GROUP BY COALESCE(NULLIF(severity, ''), 'none')"
            ).fetchall():
                key = row.get("key") or "none"
                if key in by_severity:
                    by_severity[key] = int(row.get("cnt") or 0)
                else:
                    by_severity["none"] += int(row.get("cnt") or 0)

            for row in conn.execute(
                "SELECT ch AS key, COUNT(*) AS cnt "
                "FROM notifications, jsonb_array_elements_text(target_channels) AS ch "
                "GROUP BY ch"
            ).fetchall():
                key = row.get("key")
                if key in by_channel:
                    by_channel[key] = int(row.get("cnt") or 0)

        return {
            "total": total,
            "by_status": by_status,
            "by_event_name": by_event_name,
            "by_severity": by_severity,
            "by_channel": by_channel,
        }


def _create_backend():
    if settings.database_url:
        return PostgresBackend(settings.database_url)
    return MemoryBackend()


class NotificationStore:
    def __init__(self, backend=None) -> None:
        self._lock = threading.RLock()
        self._backend = backend or _create_backend()
        self._timers: List[threading.Timer] = []
        self.dlq_publisher: Optional[Callable[[dict], None]] = None
        self._max_retries_override: Optional[int] = None
        self._retry_interval_override: Optional[float] = None

    @property
    def max_retries_override(self) -> Optional[int]:
        with self._lock:
            return self._max_retries_override

    @max_retries_override.setter
    def max_retries_override(self, value: Optional[int]) -> None:
        with self._lock:
            self._max_retries_override = value

    @property
    def retry_interval_override(self) -> Optional[float]:
        with self._lock:
            return self._retry_interval_override

    @retry_interval_override.setter
    def retry_interval_override(self, value: Optional[float]) -> None:
        with self._lock:
            self._retry_interval_override = value

    @property
    def fail_channels_override(self) -> Optional[FrozenSet[str]]:
        return delivery_mod.get_fail_channels_override()

    def effective_max_retries(self) -> int:
        with self._lock:
            if self._max_retries_override is not None:
                return self._max_retries_override
        return settings.max_retries

    def effective_retry_interval(self) -> float:
        with self._lock:
            if self._retry_interval_override is not None:
                return self._retry_interval_override
        return settings.retry_interval_seconds

    def configure_faults(
        self,
        *,
        fail_channels: object = _UNSET,
        max_retries: object = _UNSET,
        retry_interval_seconds: object = _UNSET,
    ) -> dict:
        if fail_channels is not _UNSET:
            delivery_mod.set_fail_channels_override(fail_channels)  # type: ignore[arg-type]
        with self._lock:
            if max_retries is not _UNSET:
                self._max_retries_override = max_retries  # type: ignore[assignment]
            if retry_interval_seconds is not _UNSET:
                self._retry_interval_override = retry_interval_seconds  # type: ignore[assignment]
        return self.active_faults()

    def reset_faults(self) -> dict:
        delivery_mod.set_fail_channels_override(None)
        with self._lock:
            self._max_retries_override = None
            self._retry_interval_override = None
        return self.active_faults()

    def active_faults(self) -> dict:
        with self._lock:
            max_retries_ovr = self._max_retries_override
            retry_interval_ovr = self._retry_interval_override
        return {
            "fail_channels": sorted(delivery_mod.effective_fail_channels()),
            "max_retries_override": max_retries_ovr,
            "retry_interval_override": retry_interval_ovr,
            "effective_max_retries": settings.max_retries if max_retries_ovr is None else max_retries_ovr,
            "effective_retry_interval_seconds": (
                settings.retry_interval_seconds if retry_interval_ovr is None else retry_interval_ovr
            ),
        }

    def overview(self) -> dict:
        from . import mqtt_consumer as mqtt_mod

        agg = self._backend.aggregate()
        return {
            **agg,
            "dlq_count": mqtt_mod.dlq_count(),
            "delivery_feed_count": delivery_mod.delivery_feed_count(),
            "active_faults": self.active_faults(),
            "time": iso_utc(),
        }

    @property
    def backend_name(self) -> str:
        return self._backend.backend_name

    def init(self) -> None:
        self._backend.init()
        recovered = self._backend.recover_stuck_retrying()
        if recovered:
            logger.warning("recovered %s leftover 'retrying' notifications -> marked 'failed'", recovered)

    def ping(self) -> bool:
        return self._backend.ping()

    def _derive(self, event: Event) -> Tuple[Optional[str], str, List[str]]:
        previous = self._backend.latest_for_alert(event.alert_id)
        if isinstance(event, AlertCreatedEvent):
            severity = event.severity.value
            message = event.message
            channels = (
                [c.value for c in event.target_channels]
                if event.target_channels
                else list(SEVERITY_ROUTING[severity])
            )
        elif isinstance(event, AlertEscalatedEvent):
            if event.severity is not None:
                severity = event.severity.value
            else:
                base = (previous or {}).get("severity") or "high"
                severity = "critical" if event.escalation_level >= 3 else base
            message = event.message or f"Cảnh báo {event.alert_id} đã leo thang lên cấp {event.escalation_level}"
            channels = (
                [c.value for c in event.target_channels]
                if event.target_channels
                else list(SEVERITY_ROUTING[severity])
            )
        else:
            severity = (previous or {}).get("severity")
            message = f"Cảnh báo {event.alert_id} đã được xử lý: {event.resolution_note}"
            channels = (
                [c.value for c in event.target_channels]
                if event.target_channels
                else list((previous or {}).get("target_channels") or ["telegram"])
            )
        return severity, message[:500], channels

    def process(self, event: Event, origin: str) -> Tuple[dict, bool]:
        event_id = str(event.event_id)
        with self._lock:
            existing = self._backend.get_by_event_id(event_id)
            if existing is not None:
                logger.info("duplicate event_id=%s origin=%s ignored", event_id, origin)
                return existing, True

            incoming_ts = event.timestamp.astimezone(timezone.utc)
            resolved_ts = (
                self._backend.latest_resolved_timestamp(event.alert_id)
                if event.event_name != "alert.resolved"
                else None
            )
            suppressed = resolved_ts is not None and resolved_ts >= incoming_ts

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
                "status": "duplicate_ignored" if suppressed else "queued",
                "retry_count": 0,
                "error_detail": (
                    f"SUPPRESSED_OUT_OF_ORDER: alert {event.alert_id} already resolved at "
                    f"{iso_utc(resolved_ts)} (>= {iso_utc(incoming_ts)})"
                )[:500]
                if suppressed
                else None,
                "created_at": iso_utc(),
                "delivered_at": None,
            }
            self._backend.insert({**record, "event_timestamp": incoming_ts.isoformat()})

        if suppressed:
            logger.warning(
                "suppressed out-of-order event_name=%s event_id=%s alert_id=%s origin=%s",
                record["event_name"], event_id, record["alert_id"], origin,
            )
            return dict(record), False

        logger.info(
            "accepted backend=%s event_name=%s event_id=%s alert_id=%s origin=%s channels=%s correlationId=%s",
            self.backend_name, record["event_name"], event_id, record["alert_id"], origin, channels, record["correlationId"],
        )
        self._attempt(record)
        if record["status"] == "retrying":
            self._schedule_auto_retry(record["notification_id"])
        elif record["status"] == "failed":
            self._send_to_dlq(record)
        return dict(record), False

    def _attempt(self, record: dict) -> None:
        ok, errors = deliver_all(record["target_channels"], record["alert_id"], record["message"] or "", record["correlationId"])
        with self._lock:
            max_retries = self.effective_max_retries()
            if ok:
                record.update(sent=True, status="delivered", error_detail=None, delivered_at=iso_utc())
            elif record["retry_count"] >= max_retries:
                record.update(sent=False, status="failed", error_detail="; ".join(errors)[:500])
            else:
                record.update(sent=False, status="retrying", error_detail="; ".join(errors)[:500])
            self._backend.update(record)

    def _schedule_auto_retry(self, notification_id: str) -> None:
        timer = threading.Timer(self.effective_retry_interval(), self._auto_retry, args=(notification_id,))
        timer.daemon = True
        with self._lock:
            self._timers.append(timer)
        timer.start()

    def _auto_retry(self, notification_id: str) -> None:
        with self._lock:
            record = self._backend.get_by_id(notification_id)
            if record is None or record["status"] != "retrying":
                return
            record["retry_count"] += 1
            self._backend.update(record)
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
        handled_by_consumer = False
        if self.dlq_publisher is not None:
            try:
                self.dlq_publisher(dict(record))
                if (
                    getattr(self.dlq_publisher, "__name__", None) == "publish_dlq"
                    and getattr(self.dlq_publisher, "__self__", None) is not None
                ):
                    handled_by_consumer = True
            except Exception:  # pragma: no cover
                logger.exception("failed to publish to DLQ")
        if not handled_by_consumer:
            from . import mqtt_consumer as mqtt_mod

            mqtt_mod.record_dlq_from_store(dict(record))

    def manual_retry(self, notification_id: str) -> Optional[dict]:
        with self._lock:
            record = self._backend.get_by_id(notification_id)
            if record is None:
                return None
            status = record["status"]
            if status in {"retrying", "duplicate_ignored", "queued"}:
                raise RetryLimitReached(
                    f"Notification {notification_id} đang ở trạng thái {status} nên không thể retry thủ công"
                )
            max_retries = self.effective_max_retries()
            if status == "delivered" and record["retry_count"] >= max_retries:
                raise RetryLimitReached(
                    f"Notification {notification_id} đã giao thành công và đạt tối đa {max_retries} lần retry"
                )
            record["retry_count"] += 1
            record["status"] = "retrying"
            self._backend.update(record)
        self._attempt(record)
        if record["status"] == "retrying":
            self._schedule_auto_retry(notification_id)
        elif record["status"] == "failed":
            self._send_to_dlq(record)
        return dict(record)

    def get(self, notification_id: str) -> Optional[dict]:
        return self._backend.get_by_id(notification_id)

    def page(
        self,
        limit: int,
        cursor: Optional[str] = None,
        alert_id: Optional[str] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> dict:
        offset = decode_cursor(cursor) if cursor else 0
        window, has_more = self._backend.query_page(
            limit=limit, offset=offset, alert_id=alert_id, status=status, channel=channel,
        )
        return {
            "items": window,
            "next_cursor": encode_cursor(offset + limit) if has_more else None,
            "has_more": has_more,
        }

    def reset(self) -> None:
        from . import mqtt_consumer as mqtt_mod

        with self._lock:
            for timer in self._timers:
                timer.cancel()
            self._timers.clear()
            self._max_retries_override = None
            self._retry_interval_override = None
            self._backend.clear()
        delivery_mod.set_fail_channels_override(None)
        delivery_mod.clear_delivery_feed()
        mqtt_mod.clear_dlq_buffer()


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

