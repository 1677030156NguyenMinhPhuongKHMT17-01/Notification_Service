"""Unit and integration tests for Notification Service (run inside Dockerfile `test` stage)."""

from __future__ import annotations

import json
import os
import uuid
from types import SimpleNamespace

os.environ.setdefault("RETRY_INTERVAL_SECONDS", "0.05")

import pytest
from fastapi.testclient import TestClient

from notification_app.config import settings
from notification_app.delivery import deliver_all
from notification_app.main import app
from notification_app.store import store


@pytest.fixture(autouse=True)
def clean_store():
    store.reset()
    store.dlq_publisher = None
    yield
    store.reset()
    store.dlq_publisher = None


client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {settings.auth_token}"}


def _created_payload(**overrides):
    data = {
        "event_id": str(uuid.uuid4()),
        "event_name": "alert.created",
        "correlationId": "req-test-0001",
        "source": "core-business",
        "alert_id": "ALT-001",
        "severity": "high",
        "message": "Phát hiện sự cố an ninh khẩn cấp từ Core Business",
        "target_channels": ["telegram", "email"],
        "timestamp": "2026-08-27T15:30:00Z",
    }
    data.update(overrides)
    return data


def test_health_is_public_and_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "notification-service"
    assert body["subscribed_topic"] == "campus.alerts"


def test_auth_missing_and_invalid_token_return_problem_details():
    resp_missing = client.post("/notifications", json=_created_payload())
    assert resp_missing.status_code == 401
    assert resp_missing.headers["content-type"].startswith("application/problem+json")
    assert resp_missing.json()["status"] == 401

    resp_bad = client.post(
        "/notifications",
        json=_created_payload(),
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp_bad.status_code == 401


def test_create_get_list_retry_and_idempotency():
    payload = _created_payload()
    create_resp = client.post("/notifications", json=payload, headers=AUTH_HEADERS)
    assert create_resp.status_code == 201
    created = create_resp.json()
    nid = created["notification_id"]
    assert create_resp.headers["location"] == f"/notifications/{nid}"
    assert created["status"] == "delivered"
    assert created["sent"] is True

    # Duplicate event_id -> 409 Conflict
    dup_resp = client.post("/notifications", json=payload, headers=AUTH_HEADERS)
    assert dup_resp.status_code == 409
    assert dup_resp.headers["content-type"].startswith("application/problem+json")

    # Get by id
    get_resp = client.get(f"/notifications/{nid}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["event_id"] == payload["event_id"]

    # Manual retry increments retry_count
    retry_resp = client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["retry_count"] == 1


def test_escalated_resolved_and_severity_auto_routing():
    r_low = client.post("/notifications", json=_created_payload(alert_id="ALT-1234567", correlationId="x", severity="low", target_channels=None), headers=AUTH_HEADERS)
    assert r_low.status_code == 201
    assert r_low.json()["target_channels"] == ["email"]

    r_med = client.post("/notifications", json=_created_payload(severity="medium", target_channels=None), headers=AUTH_HEADERS)
    assert r_med.status_code == 201
    assert r_med.json()["target_channels"] == ["telegram", "email"]

    r_high = client.post("/notifications", json=_created_payload(severity="high", target_channels=None), headers=AUTH_HEADERS)
    assert r_high.status_code == 201
    assert r_high.json()["target_channels"] == ["telegram", "email", "discord"]

    r1 = client.post("/notifications", json=_created_payload(severity="critical", target_channels=None), headers=AUTH_HEADERS)
    assert r1.status_code == 201
    assert r1.json()["target_channels"] == ["telegram", "email", "discord", "sms"]

    bad_esc = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": "req-test-0002",
            "source": "core-business",
            "alert_id": "ALT-001",
            "escalation_level": 6,
            "timestamp": "2026-08-27T16:10:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert bad_esc.status_code == 422

    r2 = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": "req-test-0002",
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
            "correlationId": "req-test-0002",
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


def test_validation_and_not_found_problem_details():
    bad_payload = _created_payload(alert_id="BAD", target_channels=["zalo"])
    resp = client.post("/notifications", json=bad_payload, headers=AUTH_HEADERS)
    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == 422
    assert len(body["errors"]) >= 1

    not_found = client.get("/notifications/00000000-0000-0000-0000-000000000000", headers=AUTH_HEADERS)
    assert not_found.status_code == 404


def test_deliver_all_returns_errors_when_channel_fails(monkeypatch):
    from notification_app import config, delivery

    monkeypatch.setattr(delivery, "settings", config.Settings(fail_channels=frozenset({"sms"})))
    ok, errs = deliver_all(["telegram", "sms"], "ALT-009", "test msg", "req-99")
    assert ok is False
    assert len(errs) == 1


class _RecordingMqttClient:
    def __init__(self) -> None:
        self.published = []
        self.stopped = False
        self.disconnected = False

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append((topic, json.loads(payload), qos))

    def loop_stop(self) -> None:
        self.stopped = True

    def disconnect(self) -> None:
        self.disconnected = True


def test_mqtt_consumer_processes_valid_and_ignores_duplicate_event():
    from notification_app.mqtt_consumer import MqttConsumer

    consumer = MqttConsumer()
    fake_client = _RecordingMqttClient()
    consumer._client = fake_client

    payload = _created_payload(alert_id="ALT-401")
    msg = SimpleNamespace(topic=settings.mqtt_topic, payload=json.dumps(payload).encode("utf-8"))

    consumer._on_message(None, None, msg)
    consumer._on_message(None, None, msg)  # duplicate event_id must be ignored

    listed = client.get("/notifications?alert_id=ALT-401", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    assert listed.json()["items"][0]["event_id"] == payload["event_id"]
    assert fake_client.published == []


def test_mqtt_consumer_routes_invalid_payloads_to_dlq():
    from notification_app.mqtt_consumer import MqttConsumer

    consumer = MqttConsumer()
    fake_client = _RecordingMqttClient()
    consumer._client = fake_client

    bad_json_msg = SimpleNamespace(topic=settings.mqtt_topic, payload=b"{not-json")
    bad_schema_msg = SimpleNamespace(
        topic=settings.mqtt_topic,
        payload=json.dumps(_created_payload(alert_id="INVALID")).encode("utf-8"),
    )

    consumer._on_message(None, None, bad_json_msg)
    consumer._on_message(None, None, bad_schema_msg)

    assert len(fake_client.published) == 2
    for topic, envelope, qos in fake_client.published:
        assert topic == settings.mqtt_dlq_topic
        assert qos == 1
        assert envelope["reason"] == "SCHEMA_VALIDATION_FAILED"
        assert envelope["retry_count"] == 0
        assert envelope["error_detail"]
        assert envelope["failed_at"]

    listed = client.get("/notifications", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert listed.json()["items"] == []


def test_escalated_and_resolved_optional_fields():
    esc_resp = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": "req-opt-1",
            "source": "core-business",
            "alert_id": "ALT-210",
            "escalation_level": 5,
            "severity": "critical",
            "message": "Leo thang mức tối đa cấp 5 do chưa xử lý",
            "timestamp": "2026-08-27T16:00:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert esc_resp.status_code == 201
    esc_body = esc_resp.json()
    assert esc_body["severity"] == "critical"
    assert esc_body["message"] == "Leo thang mức tối đa cấp 5 do chưa xử lý"
    assert esc_body["target_channels"] == ["telegram", "email", "discord", "sms"]

    res_resp = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.resolved",
            "correlationId": "req-opt-2",
            "source": "core-business",
            "alert_id": "ALT-211",
            "resolution_note": "OK.",
            "target_channels": ["discord", "email"],
            "timestamp": "2026-08-27T16:15:00+07:00",
        },
        headers=AUTH_HEADERS,
    )
    assert res_resp.status_code == 201
    res_body = res_resp.json()
    assert res_body["severity"] is None
    assert res_body["target_channels"] == ["discord", "email"]


def test_max_retries_zero_immediately_sends_to_dlq(monkeypatch):
    from notification_app import config, delivery as delivery_mod, store as store_mod
    from notification_app.mqtt_consumer import MqttConsumer

    monkeypatch.setattr(store_mod, "settings", config.Settings(max_retries=0, retry_interval_seconds=0.05))
    monkeypatch.setattr(delivery_mod, "settings", config.Settings(fail_channels=frozenset({"sms"})))

    consumer = MqttConsumer()
    fake_client = _RecordingMqttClient()
    consumer._client = fake_client
    store.dlq_publisher = consumer.publish_dlq

    resp = client.post(
        "/notifications",
        json=_created_payload(alert_id="ALT-300", target_channels=["sms"]),
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "failed"
    assert body["sent"] is False
    assert body["retry_count"] == 0

    assert len(fake_client.published) == 1
    topic, envelope, qos = fake_client.published[0]
    assert topic == settings.mqtt_dlq_topic
    assert qos == 1
    assert envelope["reason"] == "MAX_RETRIES_EXCEEDED"
    assert envelope["retry_count"] == 0
    assert envelope["error_detail"]
    assert envelope["failed_at"]
    assert envelope["notification"]["notification_id"] == body["notification_id"]


def test_manual_retry_on_failed_record_allows_recovery_and_exceeds_max_retries(monkeypatch):
    from notification_app import config, delivery as delivery_mod, store as store_mod
    from notification_app.mqtt_consumer import MqttConsumer

    monkeypatch.setattr(store_mod, "settings", config.Settings(max_retries=1, retry_interval_seconds=5.0))
    monkeypatch.setattr(delivery_mod, "settings", config.Settings(fail_channels=frozenset({"sms"})))

    consumer = MqttConsumer()
    fake_client = _RecordingMqttClient()
    consumer._client = fake_client
    store.dlq_publisher = consumer.publish_dlq

    resp = client.post(
        "/notifications",
        json=_created_payload(alert_id="ALT-301", target_channels=["sms"]),
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201
    nid = resp.json()["notification_id"]
    assert resp.json()["status"] == "retrying"

    # Reject manual retry while auto-retry is active
    conflict_resp = client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS)
    assert conflict_resp.status_code == 409

    # Exhaust auto-retry -> transitions to failed + DLQ
    store._auto_retry(nid)
    failed_state = client.get(f"/notifications/{nid}", headers=AUTH_HEADERS).json()
    assert failed_state["status"] == "failed"
    assert failed_state["retry_count"] == 1
    assert len(fake_client.published) == 1

    # Manual retry on failed record is allowed even when retry_count >= max_retries
    still_failing = client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS)
    assert still_failing.status_code == 200
    assert still_failing.json()["status"] == "failed"
    assert still_failing.json()["retry_count"] == 2
    assert len(fake_client.published) == 2
    assert fake_client.published[1][1]["retry_count"] == 2

    # Recover channel and retry manually again -> delivered with retry_count == 3 (> max_retries)
    monkeypatch.setattr(delivery_mod, "settings", config.Settings(fail_channels=frozenset()))
    recovered = client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS)
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "delivered"
    assert recovered.json()["sent"] is True
    assert recovered.json()["retry_count"] == 3
    assert recovered.json()["error_detail"] is None


def test_q09_out_of_order_suppression_audit_logging(monkeypatch):
    from notification_app import delivery as delivery_mod, store as store_mod

    dispatched = []
    real_deliver_all = delivery_mod.deliver_all

    def _spy_deliver_all(channels, alert_id, message, correlation_id):
        dispatched.append((alert_id, list(channels)))
        return real_deliver_all(channels, alert_id, message, correlation_id)

    monkeypatch.setattr(store_mod, "deliver_all", _spy_deliver_all)

    resolved = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.resolved",
            "correlationId": "req-q09-1",
            "source": "core-business",
            "alert_id": "ALT-060",
            "resolution_note": "Đã đóng sự cố trước khi event cũ tới.",
            "timestamp": "2026-08-27T17:00:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert resolved.status_code == 201
    assert len(dispatched) == 1

    late_created = client.post(
        "/notifications",
        json=_created_payload(alert_id="ALT-060", timestamp="2026-08-27T16:50:00Z"),
        headers=AUTH_HEADERS,
    )
    assert late_created.status_code == 201
    ooo_body = late_created.json()
    assert ooo_body["status"] == "duplicate_ignored"
    assert ooo_body["sent"] is False
    assert ooo_body["error_detail"].startswith("SUPPRESSED_OUT_OF_ORDER:")
    assert len(dispatched) == 1  # no channel dispatch happened

    audit_page = client.get("/notifications?alert_id=ALT-060&status=duplicate_ignored", headers=AUTH_HEADERS)
    assert audit_page.status_code == 200
    assert len(audit_page.json()["items"]) == 1

    retry_suppressed = client.post(f"/notifications/{ooo_body['notification_id']}/retry", headers=AUTH_HEADERS)
    assert retry_suppressed.status_code == 409

    newer_created = client.post(
        "/notifications",
        json=_created_payload(alert_id="ALT-060", timestamp="2026-08-27T18:00:00Z"),
        headers=AUTH_HEADERS,
    )
    assert newer_created.status_code == 201
    assert newer_created.json()["status"] == "delivered"
    assert len(dispatched) == 2


def test_mqtt_consumer_executor_offload_and_shutdown():
    from notification_app.mqtt_consumer import MqttConsumer

    consumer = MqttConsumer(max_workers=2)
    fake_client = _RecordingMqttClient()
    consumer._client = fake_client
    consumer._ensure_executor()

    payload = _created_payload(alert_id="ALT-402")
    msg = SimpleNamespace(topic=settings.mqtt_topic, payload=json.dumps(payload).encode("utf-8"))
    consumer._on_message(None, None, msg)
    consumer.stop()

    assert consumer._executor is None
    listed = client.get("/notifications?alert_id=ALT-402", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    assert listed.json()["items"][0]["status"] == "delivered"

