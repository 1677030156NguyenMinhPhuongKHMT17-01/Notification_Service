"""Unit tests for Notification Service Lab 05 (in-memory backend + readiness)."""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

os.environ.setdefault("RETRY_INTERVAL_SECONDS", "0.05")
os.environ.setdefault("MQTT_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "")

import pytest
from fastapi.testclient import TestClient

from notification_app.config import settings
from notification_app.delivery import deliver_all
from notification_app.main import app
from notification_app.store import store


@pytest.fixture(autouse=True)
def clean_store():
    store.reset()
    yield
    store.reset()


client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {settings.auth_token}"}


def _created_payload(**overrides):
    data = {
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.created",
        "correlationId": "req-lab05-test-01",
        "source": "core-business",
        "alert_id": "ALT-001",
        "severity": "high",
        "message": "Phát hiện sự cố an ninh khẩn cấp từ Core Business",
        "target_channels": ["telegram", "email"],
        "timestamp": "2026-08-27T15:30:00Z",
    }
    data.update(overrides)
    return data


def test_health_and_readiness_endpoints():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    ready = client.get("/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "ready"
    assert body["dependencies"]["database"]["ready"] is True


def test_create_list_retry_and_idempotency():
    payload = _created_payload()
    create_resp = client.post("/notifications", json=payload, headers=AUTH_HEADERS)
    assert create_resp.status_code == 201
    nid = create_resp.json()["notification_id"]

    dup_resp = client.post("/notifications", json=payload, headers=AUTH_HEADERS)
    assert dup_resp.status_code == 409

    retry_resp = client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["retry_count"] == 1


def test_auth_and_validation_problem_details():
    assert client.post("/notifications", json=_created_payload()).status_code == 401
    assert client.post("/notifications", json=_created_payload(), headers={"Authorization": "Bearer wrong"}).status_code == 401
    bad = client.post("/notifications", json=_created_payload(alert_id="BAD"), headers=AUTH_HEADERS)
    assert bad.status_code == 422
    assert bad.headers["content-type"].startswith("application/problem+json")


def test_deliver_all_failure(monkeypatch):
    from notification_app import config, delivery

    monkeypatch.setattr(delivery, "settings", config.Settings(fail_channels=frozenset({"sms"})))
    ok, errs = deliver_all(["telegram", "sms"], "ALT-009", "test msg", "req-99")
    assert ok is False
    assert len(errs) == 1


def test_escalated_resolved_severity_routing_and_not_found():
    expected_routing = {
        "low": ["email"],
        "medium": ["telegram", "email"],
        "high": ["telegram", "email", "discord"],
        "critical": ["telegram", "email", "discord", "sms"],
    }
    for sev, expected_channels in expected_routing.items():
        resp = client.post(
            "/notifications",
            json=_created_payload(alert_id="ALT-001", severity=sev, target_channels=None),
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["target_channels"] == expected_channels

    r2 = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": "req-lab05-test-02",
            "source": "core-business",
            "alert_id": "ALT-001",
            "escalation_level": 2,
            "timestamp": "2026-08-27T16:10:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert r2.status_code == 201

    r3 = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.resolved",
            "correlationId": "req-lab05-test-02",
            "source": "core-business",
            "alert_id": "ALT-001",
            "resolution_note": "Đội bảo vệ đã xác minh xử lý xong.",
            "timestamp": "2026-08-27T16:30:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert r3.status_code == 201

    page = client.get("/notifications/recent?limit=2", headers=AUTH_HEADERS)
    assert page.status_code == 200
    assert len(page.json()["items"]) == 2
    assert page.json()["has_more"] is True

    not_found = client.get("/notifications/00000000-0000-0000-0000-000000000000", headers=AUTH_HEADERS)
    assert not_found.status_code == 404


def test_canonical_pair04_optional_fields_and_bounds():
    # correlationId minLength=1 and >6 digit alert_id accepted
    r_created = client.post(
        "/notifications",
        json=_created_payload(correlationId="c", alert_id="ALT-1234567"),
        headers=AUTH_HEADERS,
    )
    assert r_created.status_code == 201

    # AlertEscalatedEvent optional severity & message honored; escalation_level=5 valid, 6 rejected
    r_esc = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": "req-esc-opt",
            "source": "core-business",
            "alert_id": "ALT-1234567",
            "escalation_level": 5,
            "severity": "medium",
            "message": "Leo thang cấp 5 với thông điệp tùy chọn",
            "target_channels": ["discord", "sms"],
            "timestamp": "2026-08-27T16:00:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert r_esc.status_code == 201
    esc_body = r_esc.json()
    assert esc_body["severity"] == "medium"
    assert esc_body["message"] == "Leo thang cấp 5 với thông điệp tùy chọn"
    assert esc_body["target_channels"] == ["discord", "sms"]

    bad_esc = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": "req-esc-bad",
            "source": "core-business",
            "alert_id": "ALT-1234567",
            "escalation_level": 6,
            "timestamp": "2026-08-27T16:01:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert bad_esc.status_code == 422

    # AlertResolvedEvent optional target_channels + standalone nullable severity
    r_res = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.resolved",
            "correlationId": "req-res-opt",
            "source": "core-business",
            "alert_id": "ALT-777",
            "resolution_note": "OK.",
            "target_channels": ["email", "discord"],
            "timestamp": "2026-08-27T16:20:00+07:00",
        },
        headers=AUTH_HEADERS,
    )
    assert r_res.status_code == 201
    res_body = r_res.json()
    assert res_body["severity"] is None
    assert res_body["target_channels"] == ["email", "discord"]


def test_max_retries_zero_dlq_and_manual_retry_on_failed(monkeypatch):
    from notification_app import config, delivery as delivery_mod, store as store_mod

    monkeypatch.setattr(
        delivery_mod,
        "settings",
        config.Settings(max_retries=0, retry_interval_seconds=0.05, fail_channels=frozenset({"sms"})),
    )
    monkeypatch.setattr(
        store_mod,
        "settings",
        config.Settings(max_retries=0, retry_interval_seconds=0.05, fail_channels=frozenset({"sms"})),
    )

    dlq_events = []
    store.dlq_publisher = dlq_events.append
    try:
        r_fail = client.post(
            "/notifications",
            json=_created_payload(alert_id="ALT-404", target_channels=["sms"]),
            headers=AUTH_HEADERS,
        )
        assert r_fail.status_code == 201
        failed_body = r_fail.json()
        nid = failed_body["notification_id"]
        assert failed_body["status"] == "failed"
        assert failed_body["sent"] is False
        assert failed_body["retry_count"] == 0
        assert len(dlq_events) == 1

        # Manual retry allowed while failed even though retry_count (0) >= max_retries (0)
        r_still_fail = client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS)
        assert r_still_fail.status_code == 200
        assert r_still_fail.json()["status"] == "failed"
        assert r_still_fail.json()["retry_count"] == 1
        assert len(dlq_events) == 2

        # Simulate operator fixing sms gateway; retry_count exceeds 3 and still succeeds cleanly
        monkeypatch.setattr(
            delivery_mod,
            "settings",
            config.Settings(max_retries=0, retry_interval_seconds=0.05, fail_channels=frozenset()),
        )
        for expected_count in (2, 3, 4):
            # After delivery succeeds on 2nd retry, retry_count(2) >= max_retries(0) -> 409 on 3rd
            resp = client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS)
            if expected_count == 2:
                assert resp.status_code == 200
                assert resp.json()["status"] == "delivered"
                assert resp.json()["sent"] is True
                assert resp.json()["retry_count"] == 2
                assert resp.json()["error_detail"] is None
            else:
                assert resp.status_code == 409
                break

        # Verify retry_count > 3 works cleanly on failed record too
        monkeypatch.setattr(
            delivery_mod,
            "settings",
            config.Settings(max_retries=0, retry_interval_seconds=0.05, fail_channels=frozenset({"sms"})),
        )
        r_fail2 = client.post(
            "/notifications",
            json=_created_payload(alert_id="ALT-405", target_channels=["sms"]),
            headers=AUTH_HEADERS,
        )
        nid2 = r_fail2.json()["notification_id"]
        for count in range(1, 5):
            if count == 4:
                monkeypatch.setattr(
                    delivery_mod,
                    "settings",
                    config.Settings(max_retries=0, retry_interval_seconds=0.05, fail_channels=frozenset()),
                )
            retry_resp = client.post(f"/notifications/{nid2}/retry", headers=AUTH_HEADERS)
            assert retry_resp.status_code == 200
            assert retry_resp.json()["retry_count"] == count
        assert retry_resp.json()["status"] == "delivered"
    finally:
        store.dlq_publisher = None


def test_q09_out_of_order_suppression_and_retry_conflict(monkeypatch):
    from notification_app import store as store_mod

    res = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.resolved",
            "correlationId": "req-ooo-1",
            "source": "core-business",
            "alert_id": "ALT-060",
            "resolution_note": "Resolved before delayed created arrived.",
            "timestamp": "2026-08-27T17:00:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 201

    dispatched = []
    real_deliver_all = store_mod.deliver_all

    def _spy_deliver_all(channels, alert_id, message, correlation_id):
        dispatched.append((list(channels), alert_id))
        return real_deliver_all(channels, alert_id, message, correlation_id)

    monkeypatch.setattr(store_mod, "deliver_all", _spy_deliver_all)

    # Older alert.created -> suppressed without dispatching channels
    late_created = client.post(
        "/notifications",
        json=_created_payload(alert_id="ALT-060", timestamp="2026-08-27T16:50:00Z"),
        headers=AUTH_HEADERS,
    )
    assert late_created.status_code == 201
    late_body = late_created.json()
    assert late_body["status"] == "duplicate_ignored"
    assert late_body["sent"] is False
    assert late_body["error_detail"].startswith("SUPPRESSED_OUT_OF_ORDER:")
    assert len(dispatched) == 0

    # Retrying a duplicate_ignored record returns 409 Conflict
    retry_suppressed = client.post(f"/notifications/{late_body['notification_id']}/retry", headers=AUTH_HEADERS)
    assert retry_suppressed.status_code == 409

    # Equal-timestamp alert.escalated -> also suppressed
    eq_escalated = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": "req-ooo-2",
            "source": "core-business",
            "alert_id": "ALT-060",
            "escalation_level": 2,
            "timestamp": "2026-08-27T17:00:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert eq_escalated.status_code == 201
    assert eq_escalated.json()["status"] == "duplicate_ignored"
    assert len(dispatched) == 0

    # Newer alert.created after resolved timestamp -> delivered normally
    newer_created = client.post(
        "/notifications",
        json=_created_payload(alert_id="ALT-060", timestamp="2026-08-27T17:05:00Z"),
        headers=AUTH_HEADERS,
    )
    assert newer_created.status_code == 201
    assert newer_created.json()["status"] == "delivered"
    assert len(dispatched) == 1


def test_startup_init_recovers_leftover_retrying():
    nid = str(uuid.uuid4())
    store._backend.insert({
        "notification_id": nid,
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.created",
        "correlationId": "req-restart-1",
        "source": "core-business",
        "alert_id": "ALT-610",
        "severity": "high",
        "message": "Interrupted retry row",
        "channel": "telegram",
        "target_channels": ["telegram"],
        "sent": False,
        "status": "retrying",
        "retry_count": 1,
        "error_detail": "temporary error",
        "created_at": "2026-08-27T15:30:00Z",
        "delivered_at": None,
        "event_timestamp": "2026-08-27T15:30:00+00:00",
    })
    assert client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS).status_code == 409

    store.init()
    recovered = client.get(f"/notifications/{nid}", headers=AUTH_HEADERS)
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "failed"
    assert recovered.json()["sent"] is False
    assert "interrupted" in recovered.json()["error_detail"].lower()

    retried = client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS)
    assert retried.status_code == 200
    assert retried.json()["status"] == "delivered"


def test_delivery_optional_webhooks_and_fail_channels_first(monkeypatch):
    import urllib.request
    from notification_app import config, delivery as delivery_mod

    calls = []

    class _FakeResp:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(req, timeout=None):
        calls.append((req.full_url, json.loads(req.data.decode("utf-8")), timeout))
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    # Default (no webhook URLs): mock stdout only, no HTTP requests
    monkeypatch.setattr(delivery_mod, "settings", config.Settings())
    ok_mock, errs_mock = deliver_all(["discord", "telegram"], "ALT-700", "mock test", "corr-1")
    assert ok_mock is True and errs_mock == [] and calls == []

    # FAIL_CHANNELS takes precedence over configured webhooks
    monkeypatch.setattr(
        delivery_mod,
        "settings",
        config.Settings(
            fail_channels=frozenset({"discord"}),
            discord_webhook_url="https://discord.example/hook",
            telegram_bot_token="bot123",
            telegram_chat_id="999",
            webhook_timeout_seconds=10.0,  # clamped to <= 5.0
        ),
    )
    ok_mixed, errs_mixed = deliver_all(["discord", "telegram"], "ALT-701", "webhook test", "corr-2")
    assert ok_mixed is False
    assert len(errs_mixed) == 1
    assert len(calls) == 1
    assert calls[0][0] == "https://api.telegram.org/botbot123/sendMessage"
    assert calls[0][1]["chat_id"] == "999"
    assert calls[0][2] <= 5.0

    # Discord webhook dispatches when not in FAIL_CHANNELS
    monkeypatch.setattr(
        delivery_mod,
        "settings",
        config.Settings(discord_webhook_url="https://discord.example/hook", webhook_timeout_seconds=3.0),
    )
    ok_disc, errs_disc = deliver_all(["discord"], "ALT-702", "discord msg", "corr-3")
    assert ok_disc is True and errs_disc == []
    assert calls[-1][0] == "https://discord.example/hook"
    assert "ALT-702" in calls[-1][1]["content"]
    assert calls[-1][2] == 3.0


class _RecordingMqttClient:
    def __init__(self) -> None:
        self.published = []
        self.loop_stopped = False
        self.disconnected = False

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append((topic, json.loads(payload), qos))

    def loop_stop(self) -> None:
        self.loop_stopped = True

    def disconnect(self) -> None:
        self.disconnected = True


def test_mqtt_consumer_valid_duplicate_and_dlq():
    from notification_app.mqtt_consumer import MqttConsumer

    consumer = MqttConsumer()
    fake_client = _RecordingMqttClient()
    consumer._client = fake_client

    payload = _created_payload(alert_id="ALT-502")
    valid_msg = SimpleNamespace(topic=settings.mqtt_topic, payload=json.dumps(payload).encode("utf-8"))
    consumer._on_message(None, None, valid_msg)
    consumer._on_message(None, None, valid_msg)

    bad_msg = SimpleNamespace(topic=settings.mqtt_topic, payload=b"{bad-json")
    consumer._on_message(None, None, bad_msg)

    bad_schema_msg = SimpleNamespace(
        topic=settings.mqtt_topic,
        payload=json.dumps({**payload, "event_id": str(uuid.uuid4()), "event_name": "alert.deleted"}).encode("utf-8"),
    )
    consumer._on_message(None, None, bad_schema_msg)

    consumer.wait_idle(timeout=5.0)

    listed = client.get("/notifications?alert_id=ALT-502", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    assert len(fake_client.published) == 2
    for topic, dlq_body, qos in fake_client.published:
        assert topic == settings.mqtt_dlq_topic
        assert qos == 1
        assert dlq_body["reason"] == "SCHEMA_VALIDATION_FAILED"
        assert "error_detail" in dlq_body
        assert "failed_at" in dlq_body
        assert dlq_body["retry_count"] == 0

    consumer.publish_dlq({
        "notification_id": "notif-dlq-1",
        "event_id": str(uuid.uuid4()),
        "alert_id": "ALT-502",
        "retry_count": 3,
        "error_detail": "sms gateway timeout",
    })
    assert len(fake_client.published) == 3
    max_dlq = fake_client.published[2][1]
    assert max_dlq["reason"] == "MAX_RETRIES_EXCEEDED"
    assert max_dlq["retry_count"] == 3
    assert max_dlq["error_detail"] == "sms gateway timeout"
    assert "failed_at" in max_dlq

    consumer.stop()
    assert fake_client.loop_stopped is True
    assert fake_client.disconnected is True


def test_mqtt_consumer_executor_offload_and_shutdown(monkeypatch):
    import threading
    from notification_app import mqtt_consumer as mqtt_mod

    seen_threads = []
    caller_thread = threading.get_ident()
    original_process = mqtt_mod.store.process

    def _spy_process(event, origin):
        seen_threads.append(threading.get_ident())
        return original_process(event, origin)

    monkeypatch.setattr(mqtt_mod.store, "process", _spy_process)

    consumer = mqtt_mod.MqttConsumer(max_workers=2)
    fake_client = _RecordingMqttClient()
    consumer._client = fake_client

    msg = SimpleNamespace(
        topic=settings.mqtt_topic,
        payload=json.dumps(_created_payload(alert_id="ALT-509")).encode("utf-8"),
    )
    fut = consumer._on_message(None, None, msg)
    assert fut is not None
    consumer.stop()

    assert seen_threads and seen_threads[0] != caller_thread
    assert fake_client.loop_stopped is True
    assert fake_client.disconnected is True
    assert consumer._on_message(None, None, msg) is None


def test_postgres_backend_sql_and_row_mapping(monkeypatch):
    from notification_app.store import PostgresBackend

    executed = []
    fake_row = {
        "notification_id": "notif-pg-1",
        "event_id": "evt-pg-1",
        "event_name": "alert.created",
        "correlation_id": "req-pg-1",
        "source": "core-business",
        "alert_id": "ALT-503",
        "severity": "high",
        "message": "PG row",
        "channel": "telegram+email",
        "target_channels": '["telegram", "email"]',
        "sent": True,
        "status": "delivered",
        "retry_count": 0,
        "error_detail": None,
        "created_at": "2026-11-12T16:45:00Z",
        "delivered_at": "2026-11-12T16:45:00Z",
    }

    class _FakeCursor:
        def __init__(self, one=None, many=None, rowcount=0) -> None:
            self._one = one
            self._many = many or []
            self.rowcount = rowcount

        def fetchone(self):
            return self._one

        def fetchall(self):
            return self._many

    class _FakeConn:
        def __init__(self) -> None:
            self.committed = False

        def execute(self, sql, params=None):
            executed.append((sql.strip(), params))
            if "SELECT 1" in sql:
                return _FakeCursor(one={"?column?": 1})
            if "WHERE notification_id =" in sql and sql.strip().startswith("SELECT"):
                return _FakeCursor(one=fake_row)
            if "SELECT event_timestamp FROM notifications" in sql:
                return _FakeCursor(many=[{"event_timestamp": "2026-08-27T17:00:00+00:00"}])
            if "UPDATE notifications" in sql and "WHERE status = 'retrying'" in sql:
                return _FakeCursor(rowcount=2)
            if "LIMIT %s OFFSET %s" in sql:
                return _FakeCursor(many=[fake_row, fake_row])
            return _FakeCursor()

        def commit(self) -> None:
            self.committed = True

    fake_conn = _FakeConn()

    @contextmanager
    def _fake_conn_ctx():
        yield fake_conn

    backend = PostgresBackend("postgresql://user:pass@db:5432/notificationdb")
    monkeypatch.setattr(backend, "_conn", _fake_conn_ctx)

    assert backend.ping() is True
    backend.init()
    assert fake_conn.committed is True

    sample_record = PostgresBackend._to_record(fake_row)
    assert sample_record is not None
    assert sample_record["target_channels"] == ["telegram", "email"]

    backend.insert(sample_record)
    assert json.loads(executed[-1][1]["target_channels"]) == ["telegram", "email"]

    fetched = backend.get_by_id("notif-pg-1")
    assert fetched is not None
    assert fetched["correlationId"] == "req-pg-1"

    items, has_more = backend.query_page(limit=1, offset=0, alert_id="ALT-503")
    assert len(items) == 1
    assert has_more is True

    resolved_ts = backend.latest_resolved_timestamp("ALT-503")
    assert resolved_ts is not None
    assert resolved_ts.year == 2026

    assert backend.recover_stuck_retrying() == 2

