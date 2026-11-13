"""Subscribe to `campus.alerts.dlq` and print dead-letter envelopes in real time.

Usage examples:
    python scripts/mqtt_watch_dlq.py
    python scripts/mqtt_watch_dlq.py --broker mqtt://127.0.0.1:1883 --timeout 20 --count 1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mqtt_compat import subscribe_loop  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch Pair-04 Dead-Letter Queue (campus.alerts.dlq)")
    parser.add_argument("--broker", default=os.getenv("MQTT_BROKER_URL", "mqtt://127.0.0.1:1883"))
    parser.add_argument("--topic", default=os.getenv("MQTT_DLQ_TOPIC", "campus.alerts.dlq"))
    parser.add_argument("--timeout", type=float, default=0.0, help="Seconds to wait (0 = wait until Ctrl+C)")
    parser.add_argument("--count", "--max-messages", dest="count", type=int, default=0, help="Stop after N messages (0 = unlimited)")
    parser.add_argument("--client-id", default=f"dlq-watch-{uuid.uuid4().hex[:8]}")
    args = parser.parse_args()

    print(f"[SUB] Listening broker={args.broker} topic={args.topic}", flush=True)

    def _handle(topic: str, raw: str) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            formatted = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            formatted = raw
        print(f"[DLQ {now}] topic={topic}\n{formatted}", flush=True)

    received = subscribe_loop(
        broker_url=args.broker,
        topic=args.topic,
        client_id=args.client_id,
        on_message=_handle,
        max_messages=args.count,
        timeout=args.timeout,
    )
    if args.count > 0 and received < args.count:
        print(f"[WARN] Timed out after {args.timeout}s (received {received}/{args.count})", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
