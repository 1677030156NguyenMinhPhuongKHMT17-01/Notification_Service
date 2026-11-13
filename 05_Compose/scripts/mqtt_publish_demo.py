"""Publish Pair-04 demo & fault-injection MQTT events to `campus.alerts`.

Usage examples:
    python scripts/mqtt_publish_demo.py --scenario created --alert-id ALT-501 --severity high
    python scripts/mqtt_publish_demo.py --scenario lifecycle --alert-id ALT-510
    python scripts/mqtt_publish_demo.py --scenario invalid-schema
    python scripts/mqtt_publish_demo.py --scenario ooo --alert-id ALT-520
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mqtt_compat import publish_once  # noqa: E402


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_events(args: argparse.Namespace) -> List[dict]:
    now = datetime.now(timezone.utc)
    corr_id = f"req-demo-{uuid.uuid4().hex[:10]}"
    base_id = args.event_id

    def _created(ts: datetime, eid: str | None = None) -> dict:
        return {
            "event_id": eid or str(uuid.uuid4()),
            "event_name": "alert.created",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": args.alert_id,
            "severity": args.severity,
            "message": f"Demo cảnh báo {args.alert_id} (severity={args.severity}) qua MQTT",
            "timestamp": _iso_utc(ts),
        }

    def _escalated(ts: datetime) -> dict:
        return {
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": args.alert_id,
            "escalation_level": 3,
            "severity": "critical",
            "message": f"Demo leo thang cảnh báo {args.alert_id} lên cấp 3",
            "timestamp": _iso_utc(ts),
        }

    def _resolved(ts: datetime, eid: str | None = None) -> dict:
        return {
            "event_id": eid or str(uuid.uuid4()),
            "event_name": "alert.resolved",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": args.alert_id,
            "resolution_note": "Đội vận hành đã xác minh và xử lý xong sự cố.",
            "timestamp": _iso_utc(ts),
        }

    if args.scenario == "created":
        return [_created(now, base_id)]
    if args.scenario == "escalated":
        return [_escalated(now)]
    if args.scenario == "resolved":
        return [_resolved(now, base_id)]
    if args.scenario == "lifecycle":
        return [
            _created(now - timedelta(minutes=2)),
            _escalated(now - timedelta(minutes=1)),
            _resolved(now),
        ]
    if args.scenario == "ooo":
        return [
            _resolved(now),
            _created(now - timedelta(minutes=10)),
        ]
    # invalid-schema: unsupported event_name + bad severity -> triggers SCHEMA_VALIDATION_FAILED on DLQ
    return [
        {
            "event_id": base_id or str(uuid.uuid4()),
            "event_name": "alert.deleted",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": args.alert_id,
            "severity": "EXTREME",
            "message": "Invalid demo event to test DLQ routing",
            "timestamp": _iso_utc(now),
        }
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Pair-04 demo MQTT events to campus.alerts")
    parser.add_argument("--broker", default=os.getenv("MQTT_BROKER_URL", "mqtt://127.0.0.1:1883"))
    parser.add_argument("--topic", default=os.getenv("MQTT_TOPIC", "campus.alerts"))
    parser.add_argument(
        "--scenario",
        choices=["created", "escalated", "resolved", "lifecycle", "invalid-schema", "ooo"],
        default="created",
    )
    parser.add_argument("--alert-id", default="ALT-501")
    parser.add_argument("--severity", choices=["low", "medium", "high", "critical"], default="high")
    parser.add_argument("--event-id", default=None)
    parser.add_argument("--client-id", default=f"demo-pub-{uuid.uuid4().hex[:8]}")
    args = parser.parse_args()

    events = _build_events(args)
    for idx, payload in enumerate(events, start=1):
        encoded = json.dumps(payload, ensure_ascii=False)
        publish_once(args.broker, args.topic, encoded, client_id=f"{args.client_id}-{idx}")
        print(
            f"[PUB {idx}/{len(events)}] broker={args.broker} topic={args.topic} "
            f"event_name={payload.get('event_name')} event_id={payload.get('event_id')} "
            f"alert_id={payload.get('alert_id')}",
            flush=True,
        )
        print(encoded, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
