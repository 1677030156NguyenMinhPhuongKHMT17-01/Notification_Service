"""Core Business upstream simulator for Pair 04 (Core Business -> Notification Service).

Publishes valid lifecycle events (`alert.created` with severity `high` -> auto-routes
including `discord`, `alert.escalated` with optional `severity`/`message`, and
`alert.resolved` with custom `target_channels`) plus schema-invalid and `Q09`
out-of-order fault events onto MQTT topic `campus.alerts`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mqtt_compat import publish_once  # noqa: E402


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_events(
    scenario: str,
    alert_id: str,
    ooo_alert_id: str,
    correlation_id: str | None = None,
) -> List[Dict[str, object]]:
    now = datetime.now(timezone.utc)
    corr_id = correlation_id or f"req-cb-sim-{uuid.uuid4().hex[:10]}"

    created = {
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.created",
        "correlationId": corr_id,
        "source": "core-business",
        "alert_id": alert_id,
        "severity": "high",
        "message": f"[Core Business Sim] Phát hiện sự cố mức high tại {alert_id} (auto-routing discord)",
        "timestamp": _iso_utc(now - timedelta(seconds=20)),
    }

    escalated = {
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.escalated",
        "correlationId": corr_id,
        "source": "core-business",
        "alert_id": alert_id,
        "escalation_level": 3,
        "severity": "critical",
        "message": f"[Core Business Sim] Cảnh báo {alert_id} leo thang cấp 3 (critical)",
        "timestamp": _iso_utc(now - timedelta(seconds=10)),
    }

    resolved = {
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.resolved",
        "correlationId": corr_id,
        "source": "core-business",
        "alert_id": alert_id,
        "resolution_note": "Đội trực ban Core Business xác nhận đã khắc phục sự cố.",
        "target_channels": ["email", "discord"],
        "timestamp": _iso_utc(now),
    }

    invalid_schema = {
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.deleted",
        "correlationId": corr_id,
        "source": "core-business",
        "alert_id": alert_id,
        "severity": "EXTREME",
        "message": "Schema-invalid event from Core Business simulator",
        "timestamp": _iso_utc(now),
    }

    ooo_corr = f"req-cb-ooo-{uuid.uuid4().hex[:8]}"
    ooo_resolved_first = {
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.resolved",
        "correlationId": ooo_corr,
        "source": "core-business",
        "alert_id": ooo_alert_id,
        "resolution_note": "Q09 simulator: sự cố đã đóng trước khi event tạo trễ tới broker.",
        "target_channels": ["email"],
        "timestamp": _iso_utc(now),
    }
    ooo_late_created = {
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.created",
        "correlationId": ooo_corr,
        "source": "core-business",
        "alert_id": ooo_alert_id,
        "severity": "critical",
        "message": f"Q09 simulator: event alert.created trễ cho {ooo_alert_id} (cần SUPPRESSED_OUT_OF_ORDER)",
        "timestamp": _iso_utc(now - timedelta(minutes=10)),
    }

    mapping = {
        "created": [created],
        "escalated": [escalated],
        "resolved": [resolved],
        "lifecycle": [created, escalated, resolved],
        "invalid-schema": [invalid_schema],
        "ooo": [ooo_resolved_first, ooo_late_created],
        "all": [created, escalated, resolved, invalid_schema, ooo_resolved_first, ooo_late_created],
    }
    return mapping[scenario]


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate Core Business MQTT events onto campus.alerts")
    parser.add_argument("--broker", default=os.getenv("MQTT_BROKER_URL", "mqtt://127.0.0.1:1883"))
    parser.add_argument("--topic", default=os.getenv("MQTT_TOPIC", "campus.alerts"))
    parser.add_argument(
        "--scenario",
        choices=["all", "lifecycle", "created", "escalated", "resolved", "invalid-schema", "ooo"],
        default="all",
    )
    parser.add_argument("--alert-id", default="ALT-601")
    parser.add_argument("--ooo-alert-id", default="ALT-690")
    parser.add_argument("--correlation-id", default=None)
    parser.add_argument("--delay", type=float, default=0.35, help="Delay in seconds between published events")
    parser.add_argument("--client-id", default=f"cb-sim-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary instead of line logs")
    args = parser.parse_args()

    events = build_events(args.scenario, args.alert_id, args.ooo_alert_id, args.correlation_id)
    published_summary = []

    for idx, payload in enumerate(events, start=1):
        encoded = json.dumps(payload, ensure_ascii=False)
        publish_once(args.broker, args.topic, encoded, client_id=f"{args.client_id}-{idx}")
        published_summary.append(
            {
                "index": idx,
                "topic": args.topic,
                "event_name": payload.get("event_name"),
                "event_id": payload.get("event_id"),
                "alert_id": payload.get("alert_id"),
                "correlationId": payload.get("correlationId"),
            }
        )
        if not args.json:
            print(
                f"[CB-SIM {idx}/{len(events)}] broker={args.broker} topic={args.topic} "
                f"event_name={payload.get('event_name')} alert_id={payload.get('alert_id')} "
                f"event_id={payload.get('event_id')}",
                flush=True,
            )
        if idx < len(events) and args.delay > 0:
            time.sleep(args.delay)

    if args.json:
        print(json.dumps({"broker": args.broker, "topic": args.topic, "published": published_summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
