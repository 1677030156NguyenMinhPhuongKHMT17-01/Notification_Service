"""Unit tests for the interactive Demo UI backend routes, fault overrides, and observability buffers."""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager

os.environ.setdefault("RETRY_INTERVAL_SECONDS", "0.05")
os.environ.setdefault("MQTT_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "")

import pytest
from fastapi.testclient import TestClient

from notification_app import config, delivery as delivery_mod, demo_routes, mqtt_consumer as mqtt_mod
from notification_app.config import settings
from notification_app.main import app
from notification_app.mqtt_consumer import MqttConsumer
from notification_app.store import PostgresBackend, store


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
        "correlationId": f"req-demo-test-{uuid.uuid4().hex[:6]}",
        "source": "core-business",
        "alert_id": "ALT-701",
        "severity": "high",
        "message": "Demo UI test alert notification payload",
        "timestamp": "2026-08-27T15:30:00Z",
    }
    data.update(overrides)
    return data


def test_openapi_has_zero_demo_routes():
    spec_resp = client.get("/openapi.json")
    assert spec_resp.status_code == 200
    spec = spec_resp.json()
    paths = spec["paths"]

    expected_paths = {
        "/health",
        "/ready",
        "/notifications",
        "/notifications/recent",
        "/notifications/{notification_id}",
        "/notifications/{notification_id}/retry",
    }
    assert set(paths.keys()) == expected_paths

    operation_count = sum(len(methods) for methods in paths.values())
    assert operation_count == 7

    for path in paths:
        assert not path.startswith("/demo")
        assert path != "/"

    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_demo_ui_serving_handles_missing_and_present_index(monkeypatch, tmp_path):
    monkeypatch.setattr(demo_routes, "STATIC_DIR", tmp_path)

    for route in ("/", "/demo"):
        missing = client.get(route)
        assert missing.status_code == 404
        assert missing.headers["content-type"].startswith("application/problem+json")

    index_file = tmp_path / "index.html"
    index_file.write_text("<!doctype html><html><body>Smart Campus Demo</body></html>", encoding="utf-8")

    for route in ("/", "/demo"):
        ok = client.get(route)
        assert ok.status_code == 200
        assert ok.headers["content-type"].startswith("text/html")
        assert "Smart Campus Demo" in ok.text


def test_demo_config_dev_token_hint_security(monkeypatch):
    resp = client.get("/demo-api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service_name"] == settings.service_name
    assert body["backend"] == "memory"
    assert "severity_routing" in body
    assert body["webhook_modes"] == {
        "telegram": "stdout_mock",
        "discord": "stdout_mock",
        "email": "stdout_mock",
        "sms": "stdout_mock",
    }
    assert body["dev_token_hint"] == "local-dev-token"

    monkeypatch.setattr(
        demo_routes,
        "settings",
        config.Settings(env="plugathon", auth_token="plugathon-dev-token", discord_webhook_url="https://discord.example/hook"),
    )
    monkeypatch.setattr(
        delivery_mod,
        "settings",
        config.Settings(env="plugathon", auth_token="plugathon-dev-token", discord_webhook_url="https://discord.example/hook"),
    )
    plug_body = client.get("/demo-api/config").json()
    assert plug_body["dev_token_hint"] == "plugathon-dev-token"
    assert plug_body["webhook_modes"]["discord"] == "webhook"

    monkeypatch.setattr(
        demo_routes,
        "settings",
        config.Settings(env="production", auth_token="plugathon-dev-token"),
    )
    assert client.get("/demo-api/config").json()["dev_token_hint"] is None

    monkeypatch.setattr(
        demo_routes,
        "settings",
        config.Settings(env="plugathon", auth_token="custom-secret-token-999"),
    )
    assert client.get("/demo-api/config").json()["dev_token_hint"] is None


def test_demo_protected_endpoints_require_auth():
    protected = [
        ("GET", "/demo-api/overview"),
        ("GET", "/demo-api/dlq"),
        ("GET", "/demo-api/delivery-feed"),
        ("GET", "/demo-api/faults"),
        ("POST", "/demo-api/faults"),
        ("POST", "/demo-api/faults/reset"),
        ("POST", "/demo-api/mqtt/publish"),
    ]
    for method, path in protected:
        resp = client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} did not enforce auth"


def test_demo_overview_counts_and_postgres_aggregate(monkeypatch):
    # 1. alert.created high -> [telegram, email, discord]
    r1 = client.post("/notifications", json=_created_payload(alert_id="ALT-710", severity="high"), headers=AUTH_HEADERS)
    assert r1.status_code == 201

    # 2. alert.escalated level 3 (no severity) -> derived critical -> [telegram, email, discord, sms]
    r2 = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.escalated",
            "correlationId": "req-ov-2",
            "source": "core-business",
            "alert_id": "ALT-710",
            "escalation_level": 3,
            "timestamp": "2026-08-27T15:35:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert r2.status_code == 201

    # 3. standalone alert.resolved -> severity=None -> counted under "none", target_channels=["email", "discord"]
    r3 = client.post(
        "/notifications",
        json={
            "event_id": str(uuid.uuid4()),
            "event_name": "alert.resolved",
            "correlationId": "req-ov-3",
            "source": "core-business",
            "alert_id": "ALT-711",
            "resolution_note": "Resolved standalone",
            "target_channels": ["email", "discord"],
            "timestamp": "2026-08-27T16:00:00Z",
        },
        headers=AUTH_HEADERS,
    )
    assert r3.status_code == 201

    # 4. out-of-order late alert.created -> status=duplicate_ignored, no delivery feed entries emitted
    r4 = client.post(
        "/notifications",
        json=_created_payload(alert_id="ALT-711", severity="low", timestamp="2026-08-27T15:00:00Z"),
        headers=AUTH_HEADERS,
    )
    assert r4.status_code == 201
    assert r4.json()["status"] == "duplicate_ignored"

    ov = client.get("/demo-api/overview", headers=AUTH_HEADERS)
    assert ov.status_code == 200
    body = ov.json()
    assert body["total"] == 4
    assert body["by_status"] == {
        "delivered": 3,
        "retrying": 0,
        "failed": 0,
        "duplicate_ignored": 1,
        "queued": 0,
    }
    assert body["by_event_name"] == {
        "alert.created": 2,
        "alert.escalated": 1,
        "alert.resolved": 1,
    }
    assert body["by_severity"] == {
        "low": 1,
        "medium": 0,
        "high": 1,
        "critical": 1,
        "none": 1,
    }
    assert body["by_channel"] == {
        "telegram": 2,
        "email": 4,
        "discord": 3,
        "sms": 1,
    }
    assert body["delivery_feed_count"] == 9
    assert body["dlq_count"] == 0
    assert "active_faults" in body and "time" in body

    # Verify PostgresBackend.aggregate() SQL query mapping
    class _FakeCursor:
        def __init__(self, one=None, many=None):
            self._one = one
            self._many = many or []

        def fetchone(self):
            return self._one

        def fetchall(self):
            return self._many

    class _FakeConn:
        def execute(self, sql, params=None):
            if "SELECT COUNT(*) AS cnt" in sql:
                return _FakeCursor(one={"cnt": 10})
            if "GROUP BY status" in sql:
                return _FakeCursor(many=[{"key": "delivered", "cnt": 8}, {"key": "failed", "cnt": 2}])
            if "GROUP BY event_name" in sql:
                return _FakeCursor(many=[{"key": "alert.created", "cnt": 10}])
            if "GROUP BY COALESCE" in sql:
                return _FakeCursor(many=[{"key": "high", "cnt": 7}, {"key": "none", "cnt": 3}])
            if "jsonb_array_elements_text" in sql:
                return _FakeCursor(many=[{"key": "discord", "cnt": 7}, {"key": "sms", "cnt": 2}])
            return _FakeCursor()

    @contextmanager
    def _fake_conn_ctx():
        yield _FakeConn()

    pg = PostgresBackend("postgresql://user:pass@db:5432/notificationdb")
    monkeypatch.setattr(pg, "_conn", _fake_conn_ctx)
    pg_agg = pg.aggregate()
    assert pg_agg["total"] == 10
    assert pg_agg["by_status"]["delivered"] == 8
    assert pg_agg["by_status"]["failed"] == 2
    assert pg_agg["by_severity"]["none"] == 3
    assert pg_agg["by_channel"]["discord"] == 7


def test_demo_faults_validation_dlq_feed_and_retry_recovery():
    # Invalid values return RFC 9457 422 ProblemDetails
    for bad_payload in (
        {"fail_channels": ["zalo"]},
        {"max_retries": -1},
        {"max_retries": 11},
        {"max_retries": True},
        {"retry_interval_seconds": 0.05},
        {"retry_interval_seconds": 31.0},
    ):
        bad_resp = client.post("/demo-api/faults", json=bad_payload, headers=AUTH_HEADERS)
        assert bad_resp.status_code == 422
        assert bad_resp.headers["content-type"].startswith("application/problem+json")

    # Inject SMS fault + max_retries=0
    fault_resp = client.post(
        "/demo-api/faults",
        json={"fail_channels": ["sms"], "max_retries": 0, "retry_interval_seconds": 0.2},
        headers=AUTH_HEADERS,
    )
    assert fault_resp.status_code == 200
    faults = fault_resp.json()
    assert faults["fail_channels"] == ["sms"]
    assert faults["max_retries_override"] == 0
    assert faults["effective_max_retries"] == 0
    assert faults["retry_interval_override"] == 0.2
    assert faults["effective_retry_interval_seconds"] == 0.2

    # Trigger notification targeting sms -> fails immediately and enters DLQ
    create_resp = client.post(
        "/notifications",
        json=_created_payload(alert_id="ALT-808", severity="critical", target_channels=["sms"]),
        headers=AUTH_HEADERS,
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    nid = created["notification_id"]
    assert created["status"] == "failed"
    assert created["sent"] is False

    dlq_resp = client.get("/demo-api/dlq", headers=AUTH_HEADERS)
    assert dlq_resp.status_code == 200
    dlq_body = dlq_resp.json()
    assert dlq_body["topic"] == settings.mqtt_dlq_topic
    assert dlq_body["count"] == 1
    assert dlq_body["items"][0]["reason"] == "MAX_RETRIES_EXCEEDED"
    assert dlq_body["items"][0]["notification_id"] == nid

    feed_resp = client.get("/demo-api/delivery-feed", headers=AUTH_HEADERS)
    assert feed_resp.status_code == 200
    feed_items = feed_resp.json()["items"]
    assert len(feed_items) == 1
    assert feed_items[0]["channel"] == "sms"
    assert feed_items[0]["ok"] is False
    assert feed_items[0]["mode"] == "stdout_mock"
    assert "FAIL_CHANNELS" in feed_items[0]["error"]
    assert feed_items[0]["duration_ms"] >= 0

    # Reset faults and retry -> recovers cleanly to delivered
    reset_resp = client.post("/demo-api/faults/reset", headers=AUTH_HEADERS)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["fail_channels"] == []
    assert reset_resp.json()["max_retries_override"] is None
    assert reset_resp.json()["retry_interval_override"] is None

    retry_resp = client.post(f"/notifications/{nid}/retry", headers=AUTH_HEADERS)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "delivered"
    assert retry_resp.json()["sent"] is True
    assert retry_resp.json()["retry_count"] == 1

    latest_feed = client.get("/demo-api/delivery-feed", headers=AUTH_HEADERS).json()["items"]
    assert len(latest_feed) == 2
    assert latest_feed[0]["ok"] is True
    assert latest_feed[0]["error"] is None


def test_demo_delivery_feed_bounded_max_80():
    for i in range(25):
        resp = client.post(
            "/notifications",
            json=_created_payload(
                alert_id=f"ALT-{720 + i}",
                severity="critical",
                target_channels=["telegram", "email", "discord", "sms"],
            ),
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201

    feed = client.get("/demo-api/delivery-feed", headers=AUTH_HEADERS).json()
    assert feed["count"] == 80
    assert len(feed["items"]) == 80
    # Newest item corresponds to last alert_id (ALT-744)
    assert feed["items"][0]["alert_id"] == "ALT-744"


def test_demo_mqtt_publish_503_422_and_all_4_scenarios(monkeypatch):
    # 503 when MQTT is disabled
    r_disabled = client.post("/demo-api/mqtt/publish", json={"scenario": "lifecycle"}, headers=AUTH_HEADERS)
    assert r_disabled.status_code == 503
    assert r_disabled.headers["content-type"].startswith("application/problem+json")

    # 422 when empty or invalid scenario/alert_id
    for bad in ({}, {"scenario": "unknown"}, {"scenario": "lifecycle", "alert_id": "BAD"}):
        r_bad = client.post("/demo-api/mqtt/publish", json=bad, headers=AUTH_HEADERS)
        assert r_bad.status_code == 422
        assert r_bad.headers["content-type"].startswith("application/problem+json")

    class _LoopbackMqttClient:
        def __init__(self, consumer_ref: MqttConsumer) -> None:
            self.consumer_ref = consumer_ref
            self.published = []

        def publish(self, topic: str, payload: str, qos: int = 0):
            self.published.append((topic, payload, qos))
            if topic == settings.mqtt_topic:
                self.consumer_ref._process_message(topic, payload)

            class _Info:
                rc = 0

                def wait_for_publish(self, timeout=None):
                    return None

            return _Info()

        def loop_stop(self):
            return None

        def disconnect(self):
            return None

    fake_consumer = MqttConsumer(max_workers=2)
    fake_client = _LoopbackMqttClient(fake_consumer)
    fake_consumer._client = fake_client
    fake_consumer.connected = True

    monkeypatch.setattr(demo_routes, "settings", config.Settings(mqtt_enabled=True))
    monkeypatch.setattr(mqtt_mod, "consumer", fake_consumer)
    monkeypatch.setattr(time, "sleep", lambda _sec: None)

    try:
        # 1. lifecycle
        r_life = client.post(
            "/demo-api/mqtt/publish",
            json={"scenario": "lifecycle", "alert_id": "ALT-810"},
            headers=AUTH_HEADERS,
        )
        assert r_life.status_code == 200
        life_body = r_life.json()
        assert life_body["published_count"] == 3
        assert [e["event_name"] for e in life_body["events"]] == ["alert.created", "alert.escalated", "alert.resolved"]

        # 2. duplicate_q05 -> only 1 row stored in DB
        r_dup = client.post(
            "/demo-api/mqtt/publish",
            json={"scenario": "duplicate_q05", "alert_id": "ALT-811"},
            headers=AUTH_HEADERS,
        )
        assert r_dup.status_code == 200
        assert r_dup.json()["published_count"] == 2
        dup_rows = client.get("/notifications?alert_id=ALT-811", headers=AUTH_HEADERS).json()["items"]
        assert len(dup_rows) == 1

        # 3. out_of_order_q09 -> late alert.created suppressed
        r_ooo = client.post(
            "/demo-api/mqtt/publish",
            json={"scenario": "out_of_order_q09", "alert_id": "ALT-812"},
            headers=AUTH_HEADERS,
        )
        assert r_ooo.status_code == 200
        assert r_ooo.json()["published_count"] == 2
        ooo_rows = client.get("/notifications?alert_id=ALT-812", headers=AUTH_HEADERS).json()["items"]
        assert any(row["status"] == "duplicate_ignored" for row in ooo_rows)

        # 4. invalid_schema_dlq -> captured in /demo-api/dlq as SCHEMA_VALIDATION_FAILED
        r_dlq = client.post(
            "/demo-api/mqtt/publish",
            json={"scenario": "invalid_schema_dlq", "alert_id": "ALT-813"},
            headers=AUTH_HEADERS,
        )
        assert r_dlq.status_code == 200
        assert r_dlq.json()["published_count"] == 1
        dlq_items = client.get("/demo-api/dlq", headers=AUTH_HEADERS).json()["items"]
        assert any(item["reason"] == "SCHEMA_VALIDATION_FAILED" for item in dlq_items)

        # 5. raw_payload invalid JSON -> also captured in DLQ
        r_raw = client.post(
            "/demo-api/mqtt/publish",
            json={"raw_payload": "{not-valid-json"},
            headers=AUTH_HEADERS,
        )
        assert r_raw.status_code == 200
        dlq_items_after = client.get("/demo-api/dlq", headers=AUTH_HEADERS).json()["items"]
        assert len(dlq_items_after) >= 2

        # 6. dict payload
        r_dict = client.post(
            "/demo-api/mqtt/publish",
            json={"payload": _created_payload(alert_id="ALT-814")},
            headers=AUTH_HEADERS,
        )
        assert r_dict.status_code == 200
        assert r_dict.json()["published_count"] == 1
    finally:
        fake_consumer.stop()


def test_store_reset_clears_overrides_and_buffers():
    client.post(
        "/demo-api/faults",
        json={"fail_channels": ["sms"], "max_retries": 0, "retry_interval_seconds": 0.5},
        headers=AUTH_HEADERS,
    )
    client.post(
        "/notifications",
        json=_created_payload(alert_id="ALT-899", target_channels=["sms"]),
        headers=AUTH_HEADERS,
    )
    assert client.get("/demo-api/dlq", headers=AUTH_HEADERS).json()["count"] == 1
    assert client.get("/demo-api/delivery-feed", headers=AUTH_HEADERS).json()["count"] == 1

    store.reset()

    faults = client.get("/demo-api/faults", headers=AUTH_HEADERS).json()
    assert faults["fail_channels"] == []
    assert faults["max_retries_override"] is None
    assert faults["retry_interval_override"] is None
    assert client.get("/demo-api/dlq", headers=AUTH_HEADERS).json()["count"] == 0
    assert client.get("/demo-api/delivery-feed", headers=AUTH_HEADERS).json()["count"] == 0
