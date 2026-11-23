"""Automated Plug-a-thon End-to-End (E2E) verification harness for Notification Service.

Verifies against a running API + MQTT broker:
  1. GET /health (200) and GET /ready (200, database + mqtt ready)
  2. Pair-04 MQTT handshake on `campus.alerts` -> REST `/notifications/recent`:
     - `alert.created` (`high`, omitted `target_channels` -> auto-routes including `discord`)
     - `alert.escalated` (with optional `severity` & `message`)
     - `alert.resolved` (with custom `target_channels`)
     - `Q05` duplicate `event_id` idempotency over MQTT
  3. Fault injection:
     - Schema-invalid MQTT event -> `campus.alerts.dlq` (`SCHEMA_VALIDATION_FAILED`)
     - `Q09` out-of-order late `alert.created` -> `SUPPRESSED_OUT_OF_ORDER` (`duplicate_ignored`)
     - REST `409 Conflict` (duplicate `event_id`), `401 Unauthorized` (invalid/missing token),
       `422 Unprocessable Entity` (invalid channel `zalo`), and `POST /notifications/{id}/retry`
  4. Optional `--with-compose-dlq-recovery` (or `--phase fail-only` / `--phase recover-only`):
     - Forces transient channel failure (`FAIL_CHANNELS=sms`, `MAX_RETRIES=0`) -> `status=failed`
       + `campus.alerts.dlq` (`MAX_RETRIES_EXCEEDED`), clears fault env, and recovers via
       `POST /notifications/{id}/retry` -> `status=delivered`, `retry_count=1`.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mqtt_compat import publish_once, subscribe_loop  # noqa: E402

LAB06_DIR = Path(__file__).resolve().parents[1]


def _iso_utc(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_json(
    method: str,
    url: str,
    token: Optional[str] = None,
    payload: Optional[dict] = None,
    timeout: float = 5.0,
) -> Tuple[int, Dict[str, str], Any]:
    headers: Dict[str, str] = {}
    body_bytes: Optional[bytes] = None
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp_headers, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        resp_headers = {k.lower(): v for k, v in exc.headers.items()}
        parsed = None
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
        return exc.code, resp_headers, parsed


class _DlqCollector:
    def __init__(self, broker: str, topic: str) -> None:
        self.broker = broker
        self.topic = topic
        self.messages: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop = False
        self._thread: Optional[threading.Thread] = None

    def start(self, listen_seconds: float = 60.0) -> None:
        def _on_msg(_topic: str, raw: str) -> None:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw}
            with self._lock:
                self.messages.append(parsed)

        def _runner() -> None:
            subscribe_loop(
                broker_url=self.broker,
                topic=self.topic,
                client_id=f"e2e-dlq-watch-{uuid.uuid4().hex[:8]}",
                on_message=_on_msg,
                timeout=listen_seconds,
            )

        self._thread = threading.Thread(target=_runner, daemon=True)
        self._thread.start()
        time.sleep(0.8)

    def wait_for(self, event_id: str, timeout: float = 15.0) -> Dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                for msg in self.messages:
                    if not isinstance(msg, dict):
                        continue
                    if msg.get("event_id") == event_id:
                        return msg
                    nested_event = msg.get("event")
                    if isinstance(nested_event, dict) and nested_event.get("event_id") == event_id:
                        return msg
                    if event_id in str(msg.get("original_payload", "")):
                        return msg
            time.sleep(0.25)
        raise TimeoutError(f"Timed out waiting for event_id={event_id} on DLQ topic {self.topic}")


def _poll_recent_by_event_id(
    base_url: str,
    token: str,
    event_id: str,
    timeout: float = 15.0,
    limit: int = 50,
    expected_statuses: Optional[Tuple[str, ...]] = ("delivered", "failed", "duplicate_ignored"),
) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    url = f"{base_url.rstrip('/')}/notifications/recent?limit={limit}"
    last_seen: Optional[Dict[str, Any]] = None
    while time.monotonic() < deadline:
        code, _headers, body = _http_json("GET", url, token=token)
        if code == 200 and isinstance(body, dict):
            for item in body.get("items", []):
                if item.get("event_id") == event_id:
                    last_seen = item
                    if expected_statuses is None or item.get("status") in expected_statuses:
                        return item
        time.sleep(0.25)
    raise TimeoutError(
        f"Timed out polling /notifications/recent for event_id={event_id} "
        f"(expected_statuses={expected_statuses}, last_seen={last_seen})"
    )


def _wait_ready(base_url: str, timeout: float = 30.0) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    url = f"{base_url.rstrip('/')}/ready"
    last_body: Any = None
    while time.monotonic() < deadline:
        try:
            code, _headers, body = _http_json("GET", url, timeout=3.0)
            last_body = body
            if (
                code == 200
                and isinstance(body, dict)
                and body.get("status") == "ready"
                and body.get("dependencies", {}).get("database", {}).get("ready") is True
                and body.get("dependencies", {}).get("mqtt", {}).get("connected") is True
            ):
                return body
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Service did not become ready within {timeout}s; last={last_body}")


def _recreate_compose_api(compose_file: Path, env_overrides: Dict[str, str]) -> None:
    env = os.environ.copy()
    env.update(env_overrides)
    cmd = [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "up",
        "-d",
        "--no-deps",
        "--wait",
        "api",
    ]
    proc = subprocess.run(cmd, cwd=str(compose_file.parent), env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Compose recreate failed (exit={proc.returncode}): {proc.stderr or proc.stdout}"
        )


def _fresh_alert_id(prefix: str = "ALT-6") -> str:
    return f"{prefix}{random.randint(10, 99)}{random.randint(0, 9)}"


def main() -> int:
    default_port = os.getenv("APP_PORT", "8000")
    parser = argparse.ArgumentParser(description="Run Lab 06 Plug-a-thon automated E2E suite")
    parser.add_argument("--base-url", default=f"http://127.0.0.1:{default_port}")
    parser.add_argument("--broker", default=os.getenv("MQTT_BROKER_URL", "mqtt://127.0.0.1:1883"))
    parser.add_argument("--topic", default=os.getenv("MQTT_TOPIC", "campus.alerts"))
    parser.add_argument("--dlq-topic", default=os.getenv("MQTT_DLQ_TOPIC", "campus.alerts.dlq"))
    parser.add_argument("--token", default=os.getenv("AUTH_TOKEN", "plugathon-dev-token"))
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--with-compose-dlq-recovery",
        action="store_true",
        help="Recreate api with FAIL_CHANNELS=sms MAX_RETRIES=0 to test MAX_RETRIES_EXCEEDED DLQ and /retry recovery",
    )
    parser.add_argument(
        "--compose-file",
        default=str(LAB06_DIR / "docker-compose.yml"),
        help="Compose file used with --with-compose-dlq-recovery",
    )
    parser.add_argument("--json-out", default="", help="Optional path to save diagnostic JSON summary")
    parser.add_argument("--json", action="store_true", help="Print JSON summary block")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    results: List[Dict[str, Any]] = []
    client_prefix = f"e2e-{uuid.uuid4().hex[:8]}"

    def _record(name: str, ok: bool, details: Dict[str, Any]) -> None:
        results.append({"check": name, "ok": ok, **details})
        status_label = "PASS" if ok else "FAIL"
        summary_kv = " ".join(f"{k}={v}" for k, v in details.items())
        print(f"[{status_label}] {name}: {summary_kv}", flush=True)

    dlq_collector = _DlqCollector(args.broker, args.dlq_topic)
    dlq_collector.start(listen_seconds=max(90.0, args.timeout * 4))

    try:
        # 1. /health and /ready
        code, _hdrs, health = _http_json("GET", f"{base_url}/health")
        assert code == 200 and isinstance(health, dict) and health.get("status") == "ok", f"/health failed: {code} {health}"
        _record("health", True, {"http": code, "status": health.get("status"), "topic": health.get("subscribed_topic")})

        ready = _wait_ready(base_url, timeout=args.timeout)
        _record(
            "ready",
            True,
            {
                "status": ready.get("status"),
                "db_ready": ready["dependencies"]["database"]["ready"],
                "mqtt_connected": ready["dependencies"]["mqtt"]["connected"],
            },
        )

        # 2. Pair-04 MQTT lifecycle: created (high -> discord), escalated (optional fields), resolved (custom channels)
        happy_alert_id = _fresh_alert_id("ALT-6")
        corr_id = f"req-e2e-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        ev_created_id = str(uuid.uuid4())
        ev_created = {
            "event_id": ev_created_id,
            "event_name": "alert.created",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": happy_alert_id,
            "severity": "high",
            "message": f"E2E cảnh báo mức high cho {happy_alert_id}",
            "timestamp": _iso_utc(now - timedelta(seconds=15)),
        }
        publish_once(args.broker, args.topic, json.dumps(ev_created), client_id=f"{client_prefix}-1")
        created_rec = _poll_recent_by_event_id(base_url, args.token, ev_created_id, timeout=args.timeout)
        assert created_rec["status"] == "delivered" and created_rec["sent"] is True, (
            f"Expected delivered alert.created, got {created_rec}"
        )
        assert "discord" in created_rec["target_channels"], f"Expected discord auto-routing, got {created_rec['target_channels']}"
        _record(
            "mqtt_alert_created_high_routing",
            True,
            {
                "alert_id": happy_alert_id,
                "notification_id": created_rec["notification_id"],
                "channels": created_rec["target_channels"],
            },
        )

        # Q05 duplicate event_id over MQTT -> skipped idempotently
        publish_once(args.broker, args.topic, json.dumps(ev_created), client_id=f"{client_prefix}-dup")
        time.sleep(0.8)
        code, _hdrs, dup_page = _http_json(
            "GET",
            f"{base_url}/notifications?alert_id={urllib.parse.quote(happy_alert_id)}&limit=20",
            token=args.token,
        )
        assert code == 200 and isinstance(dup_page, dict), (
            f"Expected HTTP 200 querying duplicate alert_id={happy_alert_id}, got {code} {dup_page}"
        )
        matching = [item for item in dup_page.get("items", []) if item.get("event_id") == ev_created_id]
        assert len(matching) == 1, f"Expected 1 record for duplicate MQTT event_id, got {len(matching)}"
        _record("mqtt_q05_duplicate_idempotency", True, {"event_id": ev_created_id, "stored_rows": len(matching)})

        ev_escalated_id = str(uuid.uuid4())
        ev_escalated = {
            "event_id": ev_escalated_id,
            "event_name": "alert.escalated",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": happy_alert_id,
            "escalation_level": 3,
            "severity": "critical",
            "message": f"E2E leo thang cấp 3 cho {happy_alert_id}",
            "timestamp": _iso_utc(now - timedelta(seconds=8)),
        }
        publish_once(args.broker, args.topic, json.dumps(ev_escalated), client_id=f"{client_prefix}-2")
        esc_rec = _poll_recent_by_event_id(base_url, args.token, ev_escalated_id, timeout=args.timeout)
        assert esc_rec["status"] == "delivered" and esc_rec["severity"] == "critical", (
            f"Expected delivered critical alert.escalated, got {esc_rec}"
        )
        assert esc_rec["message"] == ev_escalated["message"], (
            f"Expected escalated message={ev_escalated['message']!r}, got {esc_rec.get('message')!r}"
        )
        _record(
            "mqtt_alert_escalated_optional_fields",
            True,
            {
                "notification_id": esc_rec["notification_id"],
                "severity": esc_rec["severity"],
                "channels": esc_rec["target_channels"],
            },
        )

        ev_resolved_id = str(uuid.uuid4())
        ev_resolved = {
            "event_id": ev_resolved_id,
            "event_name": "alert.resolved",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": happy_alert_id,
            "resolution_note": "E2E xác minh xử lý xong sự cố.",
            "target_channels": ["email", "discord"],
            "timestamp": _iso_utc(now),
        }
        publish_once(args.broker, args.topic, json.dumps(ev_resolved), client_id=f"{client_prefix}-3")
        res_rec = _poll_recent_by_event_id(base_url, args.token, ev_resolved_id, timeout=args.timeout)
        assert res_rec["status"] == "delivered" and res_rec["target_channels"] == ["email", "discord"], (
            f"Expected delivered alert.resolved with ['email', 'discord'], got {res_rec}"
        )
        _record(
            "mqtt_alert_resolved_custom_channels",
            True,
            {
                "notification_id": res_rec["notification_id"],
                "channels": res_rec["target_channels"],
            },
        )

        # 3. Schema-invalid MQTT -> campus.alerts.dlq SCHEMA_VALIDATION_FAILED
        bad_event_id = str(uuid.uuid4())
        bad_payload = {
            "event_id": bad_event_id,
            "event_name": "alert.deleted",
            "correlationId": corr_id,
            "source": "core-business",
            "alert_id": happy_alert_id,
            "severity": "EXTREME",
            "timestamp": _iso_utc(now),
        }
        publish_once(args.broker, args.topic, json.dumps(bad_payload), client_id=f"{client_prefix}-bad")
        dlq_schema = dlq_collector.wait_for(bad_event_id, timeout=args.timeout)
        assert dlq_schema.get("reason") == "SCHEMA_VALIDATION_FAILED", f"Unexpected DLQ reason: {dlq_schema}"
        assert dlq_schema.get("retry_count") == 0 and "failed_at" in dlq_schema, (
            f"Expected retry_count=0 and failed_at in DLQ payload, got {dlq_schema}"
        )
        _record(
            "fault_schema_invalid_dlq",
            True,
            {"event_id": bad_event_id, "reason": dlq_schema["reason"], "dlq_topic": args.dlq_topic},
        )

        # 4. Q09 Out-of-Order late alert.created -> SUPPRESSED_OUT_OF_ORDER
        ooo_alert_id = _fresh_alert_id("ALT-9")
        ooo_resolved_id = str(uuid.uuid4())
        ooo_created_id = str(uuid.uuid4())
        publish_once(
            args.broker,
            args.topic,
            json.dumps(
                {
                    "event_id": ooo_resolved_id,
                    "event_name": "alert.resolved",
                    "correlationId": f"req-ooo-{uuid.uuid4().hex[:6]}",
                    "source": "core-business",
                    "alert_id": ooo_alert_id,
                    "resolution_note": "Đã xử lý trước khi event created tới.",
                    "timestamp": _iso_utc(now),
                }
            ),
            client_id=f"{client_prefix}-ooo1",
        )
        _poll_recent_by_event_id(base_url, args.token, ooo_resolved_id, timeout=args.timeout)

        publish_once(
            args.broker,
            args.topic,
            json.dumps(
                {
                    "event_id": ooo_created_id,
                    "event_name": "alert.created",
                    "correlationId": f"req-ooo-{uuid.uuid4().hex[:6]}",
                    "source": "core-business",
                    "alert_id": ooo_alert_id,
                    "severity": "critical",
                    "message": "Q09 delayed created payload",
                    "timestamp": _iso_utc(now - timedelta(minutes=10)),
                }
            ),
            client_id=f"{client_prefix}-ooo2",
        )
        ooo_rec = _poll_recent_by_event_id(base_url, args.token, ooo_created_id, timeout=args.timeout)
        assert ooo_rec["status"] == "duplicate_ignored" and ooo_rec["sent"] is False, (
            f"Expected suppressed duplicate_ignored for Q09 late created, got {ooo_rec}"
        )
        assert str(ooo_rec.get("error_detail") or "").startswith("SUPPRESSED_OUT_OF_ORDER:"), (
            f"Expected SUPPRESSED_OUT_OF_ORDER error_detail, got {ooo_rec.get('error_detail')!r}"
        )
        _record(
            "fault_q09_out_of_order_suppressed",
            True,
            {
                "alert_id": ooo_alert_id,
                "notification_id": ooo_rec["notification_id"],
                "status": ooo_rec["status"],
            },
        )

        # 5. REST faults: 409 duplicate event_id, 401 invalid token, 422 invalid channel
        rest_event_id = str(uuid.uuid4())
        rest_payload = {
            "event_id": rest_event_id,
            "event_name": "alert.created",
            "correlationId": f"req-rest-{uuid.uuid4().hex[:6]}",
            "source": "core-business",
            "alert_id": _fresh_alert_id("ALT-7"),
            "severity": "medium",
            "message": "REST fallback E2E verification event",
            "timestamp": _iso_utc(now),
        }
        c1, _h1, b1 = _http_json("POST", f"{base_url}/notifications", token=args.token, payload=rest_payload)
        assert c1 == 201 and b1["target_channels"] == ["telegram", "email"], f"Expected 201 + [telegram, email], got {c1} {b1}"

        c_dup, _h_dup, b_dup = _http_json("POST", f"{base_url}/notifications", token=args.token, payload=rest_payload)
        assert c_dup == 409 and isinstance(b_dup, dict) and b_dup.get("status") == 409, (
            f"Expected 409 ProblemDetails on duplicate event_id, got {c_dup} {b_dup}"
        )
        _record("rest_duplicate_event_409", True, {"http": c_dup, "event_id": rest_event_id})

        c_401, _h_401, b_401 = _http_json(
            "POST", f"{base_url}/notifications", token="invalid-plugathon-token", payload=rest_payload
        )
        assert c_401 == 401 and isinstance(b_401, dict) and b_401.get("status") == 401, (
            f"Expected 401 ProblemDetails on invalid token, got {c_401} {b_401}"
        )
        _record("rest_invalid_token_401", True, {"http": c_401})

        bad_channel_payload = {**rest_payload, "event_id": str(uuid.uuid4()), "target_channels": ["zalo"]}
        c_422, h_422, b_422 = _http_json("POST", f"{base_url}/notifications", token=args.token, payload=bad_channel_payload)
        assert c_422 == 422 and "application/problem+json" in h_422.get("content-type", ""), (
            f"Expected 422 application/problem+json on invalid channel, got {c_422} headers={h_422} body={b_422}"
        )
        assert isinstance(b_422, dict) and b_422.get("status") == 422, (
            f"Expected status=422 in ProblemDetails body, got {b_422}"
        )
        _record("rest_invalid_channel_422", True, {"http": c_422})

        rest_nid = b1["notification_id"]
        c_det, _h_det, b_det = _http_json("GET", f"{base_url}/notifications/{rest_nid}", token=args.token)
        assert c_det == 200 and isinstance(b_det, dict) and b_det.get("notification_id") == rest_nid, (
            f"Expected 200 matching notification_id={rest_nid}, got {c_det} {b_det}"
        )
        c_man, _h_man, b_man = _http_json("POST", f"{base_url}/notifications/{rest_nid}/retry", token=args.token)
        assert c_man == 200 and isinstance(b_man, dict) and b_man.get("retry_count", 0) >= 1, (
            f"Expected 200 retry_count >= 1 on manual retry, got {c_man} {b_man}"
        )
        _record(
            "rest_detail_and_manual_retry",
            True,
            {"notification_id": rest_nid, "retry_count": b_man["retry_count"], "status": b_man["status"]},
        )

        # 6. Optional transient channel failure -> MAX_RETRIES_EXCEEDED DLQ + POST /notifications/{id}/retry recovery
        if args.with_compose_dlq_recovery:
            compose_path = Path(args.compose_file).resolve()
            _recreate_compose_api(compose_path, {"FAIL_CHANNELS": "sms", "MAX_RETRIES": "0"})
            try:
                _wait_ready(base_url, timeout=30.0)
                time.sleep(0.5)

                fail_event_id = str(uuid.uuid4())
                fail_alert_id = _fresh_alert_id("ALT-8")
                publish_once(
                    args.broker,
                    args.topic,
                    json.dumps(
                        {
                            "event_id": fail_event_id,
                            "event_name": "alert.created",
                            "correlationId": f"req-dlq-rec-{uuid.uuid4().hex[:6]}",
                            "source": "core-business",
                            "alert_id": fail_alert_id,
                            "severity": "critical",
                            "message": f"E2E transient sms failure for {fail_alert_id}",
                            "target_channels": ["sms"],
                            "timestamp": _iso_utc(),
                        }
                    ),
                    client_id=f"{client_prefix}-fail",
                )
                failed_rec = _poll_recent_by_event_id(
                    base_url,
                    args.token,
                    fail_event_id,
                    timeout=args.timeout,
                    expected_statuses=("failed",),
                )
                assert failed_rec["status"] == "failed" and failed_rec["sent"] is False, (
                    f"Expected failed status with sent=False, got {failed_rec}"
                )
                dlq_max = dlq_collector.wait_for(fail_event_id, timeout=args.timeout)
                assert dlq_max.get("reason") == "MAX_RETRIES_EXCEEDED", f"Expected MAX_RETRIES_EXCEEDED, got {dlq_max}"
            finally:
                # Always clear transient channel fault and wait for stack readiness
                _recreate_compose_api(compose_path, {"FAIL_CHANNELS": "", "MAX_RETRIES": "3"})
                _wait_ready(base_url, timeout=30.0)

            nid_failed = failed_rec["notification_id"]
            c_rec, _h_rec, b_rec = _http_json(
                "POST", f"{base_url}/notifications/{nid_failed}/retry", token=args.token
            )
            assert (
                c_rec == 200
                and isinstance(b_rec, dict)
                and b_rec.get("status") == "delivered"
                and b_rec.get("sent") is True
                and b_rec.get("retry_count", 0) >= 1
            ), f"Expected 200 recovered delivered notification on /retry, got {c_rec} {b_rec}"
            c_pers, _h_pers, _b_pers = _http_json(
                "GET", f"{base_url}/notifications/{created_rec['notification_id']}", token=args.token
            )
            assert c_pers == 200, (
                f"Expected persisted notification {created_rec['notification_id']} to remain accessible (200), got {c_pers}"
            )
            _record(
                "fault_max_retries_dlq_and_manual_retry_recovery",
                True,
                {
                    "notification_id": nid_failed,
                    "dlq_reason": dlq_max["reason"],
                    "recovered_status": b_rec["status"],
                    "retry_count": b_rec["retry_count"],
                },
            )

        summary = {
            "ok": True,
            "base_url": base_url,
            "broker": args.broker,
            "passed": len(results),
            "total": len(results),
            "checks": results,
        }
        if args.json_out:
            out_path = Path(args.json_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"E2E SUMMARY: {summary['passed']}/{summary['total']} checks PASSED", flush=True)
        return 0
    except Exception as exc:
        summary = {
            "ok": False,
            "base_url": base_url,
            "broker": args.broker,
            "error": str(exc),
            "passed": sum(1 for r in results if r["ok"]),
            "total": len(results),
            "checks": results,
        }
        if args.json_out:
            out_path = Path(args.json_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[FAIL] E2E aborted: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
