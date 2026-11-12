"""Unit and integration tests for Notification Service (run inside Dockerfile `test` stage)."""

from __future__ import annotations

import os
import uuid

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
    yield
    store.reset()


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
    r1 = client.post("/notifications", json=_created_payload(severity="critical", target_channels=None), headers=AUTH_HEADERS)
    assert r1.status_code == 201
    assert r1.json()["target_channels"] == ["telegram", "email", "sms"]

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

