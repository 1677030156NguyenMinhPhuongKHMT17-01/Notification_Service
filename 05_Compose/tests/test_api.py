"""Unit tests for Notification Service Lab 05 (in-memory backend + readiness)."""

from __future__ import annotations

import os
import uuid

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

