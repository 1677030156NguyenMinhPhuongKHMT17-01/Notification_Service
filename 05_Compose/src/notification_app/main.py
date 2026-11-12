"""Notification Service (Nhóm 6) – FastAPI implementation for Lab 05 (Docker Compose).

Orchestrated with PostgreSQL (`db`) and Mosquitto (`mqtt-broker`):
    GET  /health                                  (OpenAPI 3.1 HealthStatus + live DB ping)
    GET  /ready                                   (extended component readiness: db & mqtt)
    POST /notifications                           (REST sync fallback, persisted in PostgreSQL)
    GET  /notifications                           (cursor pagination + filters)
    GET  /notifications/recent                    (cursor pagination)
    GET  /notifications/{notification_id}
    POST /notifications/{notification_id}/retry   (manual retry, max 3)
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Body, Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import mqtt_consumer
from .config import settings
from .models import (
    ALERT_ID_PATTERN,
    DeliveryStatus,
    HealthStatus,
    NotificationChannel,
    NotificationEventRequest,
    NotificationLog,
    NotificationPage,
    Problem,
    iso_utc,
)
from .store import InvalidCursor, RetryLimitReached, store

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s level=%(levelname)s logger=%(name)s %(message)s",
)
logger = logging.getLogger("notification.api")

PROBLEM_BASE = "https://campus.local/errors"
PROBLEM_MEDIA_TYPE = "application/problem+json"

ERROR_CODES = {
    "missing": "REQUIRED",
    "union_tag_not_found": "REQUIRED",
    "union_tag_invalid": "ENUM_MISMATCH",
    "enum": "ENUM_MISMATCH",
    "literal_error": "ENUM_MISMATCH",
    "string_pattern_mismatch": "PATTERN_MISMATCH",
    "uuid_parsing": "FORMAT_INVALID",
    "uuid_type": "FORMAT_INVALID",
    "datetime_parsing": "FORMAT_INVALID",
    "datetime_from_date_parsing": "FORMAT_INVALID",
    "timezone_aware": "FORMAT_INVALID",
    "string_too_short": "TOO_SHORT",
    "string_too_long": "TOO_LONG",
    "too_short": "TOO_FEW_ITEMS",
    "too_long": "TOO_MANY_ITEMS",
    "extra_forbidden": "UNKNOWN_FIELD",
    "greater_than_equal": "OUT_OF_RANGE",
    "less_than_equal": "OUT_OF_RANGE",
    "int_parsing": "TYPE_MISMATCH",
    "string_type": "TYPE_MISMATCH",
    "json_invalid": "INVALID_JSON",
    "value_error": "INVALID_VALUE",
}


class ProblemException(Exception):
    def __init__(self, status_code: int, slug: str, title: str, detail: str, headers: Optional[dict] = None):
        self.status_code = status_code
        self.slug = slug
        self.title = title
        self.detail = detail
        self.headers = headers


def problem_response(
    request: Request,
    status_code: int,
    slug: str,
    title: str,
    detail: Optional[str],
    errors: Optional[List[dict]] = None,
    headers: Optional[dict] = None,
) -> JSONResponse:
    body = Problem(
        type=f"{PROBLEM_BASE}/{slug}",
        title=title,
        status=status_code,
        detail=detail[:500] if detail else None,
        instance=str(request.url),
        errors=errors or [],
    ).model_dump()
    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_MEDIA_TYPE, headers=headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "starting service=%s version=%s env=%s backend=%s mqtt_enabled=%s broker=%s topic=%s",
        settings.service_name, settings.service_version, settings.env,
        store.backend_name, settings.mqtt_enabled, settings.mqtt_broker_url, settings.mqtt_topic,
    )
    store.init()
    mqtt_consumer.start_consumer()
    yield
    mqtt_consumer.stop_consumer()
    logger.info("service stopped")


app = FastAPI(
    title="Smart Campus — Notification Service API (Nhóm 6)",
    version=settings.service_version,
    description="Lab 05 – Multi-container Notification Service (API + PostgreSQL + MQTT Broker).",
    lifespan=lifespan,
)


# ---------------------------------------------------------------- middleware
@app.middleware("http")
async def access_log(request: Request, call_next):
    started = time.perf_counter()
    trace_id = request.headers.get("x-trace-id", "-")
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if trace_id != "-":
        response.headers["X-Trace-Id"] = trace_id
    logger.info(
        "http method=%s path=%s status=%s duration_ms=%.1f trace_id=%s",
        request.method, request.url.path, response.status_code, elapsed_ms, trace_id,
    )
    return response


# ---------------------------------------------------------------- error handlers
@app.exception_handler(ProblemException)
async def handle_problem(request: Request, exc: ProblemException) -> JSONResponse:
    return problem_response(request, exc.status_code, exc.slug, exc.title, exc.detail, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    raw_errors = exc.errors()
    field_errors: List[dict] = []
    body_error = False
    invalid_json = False

    for err in raw_errors[:50]:
        loc = list(err.get("loc", []))
        etype = err.get("type", "value_error")
        if loc and loc[0] == "body":
            body_error = True
            loc = loc[1:]
            if loc and isinstance(loc[0], str) and loc[0].startswith("alert."):
                loc = loc[1:]
        elif loc and loc[0] in {"query", "path", "header"}:
            loc = loc[1:]
        if etype == "json_invalid":
            invalid_json = True
        field = ".".join(str(part) for part in loc) or "body"
        message = f"{field}: {err.get('msg', 'invalid value')}"
        field_errors.append({
            "field": field[:80],
            "code": ERROR_CODES.get(etype, etype.upper()[:80]),
            "message": message[:200],
        })

    if body_error and not invalid_json:
        status_code, slug, title = 422, "unprocessable", "Vi phạm ràng buộc nghiệp vụ"
        detail = "Payload không đúng JSON Schema của sự kiện thông báo (event-contract-04)"
    else:
        status_code, slug, title = 400, "validation", "Dữ liệu không hợp lệ"
        detail = "Request sai định dạng JSON hoặc tham số truy vấn không hợp lệ"

    summary = "; ".join(e["message"] for e in field_errors[:3])
    return problem_response(request, status_code, slug, title, f"{detail}. {summary}", errors=field_errors)


@app.exception_handler(StarletteHTTPException)
async def handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    slugs = {404: ("not-found", "Không tìm thấy tài nguyên"), 405: ("method-not-allowed", "Phương thức không được hỗ trợ")}
    slug, title = slugs.get(exc.status_code, ("http-error", "Lỗi HTTP"))
    return problem_response(request, exc.status_code, slug, title, str(exc.detail), headers=getattr(exc, "headers", None))


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return problem_response(request, 500, "internal-server-error", "Lỗi máy chủ nội bộ", "Đã xảy ra lỗi không mong muốn")


# ---------------------------------------------------------------- security
def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    challenge = {"WWW-Authenticate": 'Bearer realm="notification-service"'}
    if not authorization:
        raise ProblemException(401, "unauthorized", "Chưa xác thực", "Thiếu header Authorization: Bearer <token>", challenge)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token.strip() != settings.auth_token:
        raise ProblemException(401, "unauthorized", "Chưa xác thực", "Bearer token không hợp lệ", challenge)


PROBLEM_RESPONSES = {
    code: {"model": Problem, "content": {PROBLEM_MEDIA_TYPE: {}}}
    for code in (400, 401, 404, 409, 422, 500)
}


# ---------------------------------------------------------------- routes
@app.get("/health", response_model=HealthStatus, tags=["health"])
def get_health() -> HealthStatus:
    if not store.ping():
        raise ProblemException(503, "service-unavailable", "Cơ sở dữ liệu chưa sẵn sàng", "Không thể kết nối PostgreSQL")
    return HealthStatus(
        status="ok",
        service=settings.service_name,
        mqtt_broker=settings.mqtt_broker_url,
        subscribed_topic=settings.mqtt_topic,
        time=iso_utc(),
    )


@app.get("/ready", tags=["health"])
def get_readiness() -> JSONResponse:
    db_ok = store.ping()
    mqtt_ok = True if not settings.mqtt_enabled else bool(mqtt_consumer.consumer and mqtt_consumer.consumer.connected)
    ready = db_ok and mqtt_ok
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ready" if ready else "degraded",
            "service": settings.service_name,
            "version": settings.service_version,
            "dependencies": {
                "database": {"backend": store.backend_name, "ready": db_ok},
                "mqtt": {
                    "enabled": settings.mqtt_enabled,
                    "broker": settings.mqtt_broker_url,
                    "topic": settings.mqtt_topic,
                    "connected": mqtt_ok,
                },
            },
            "time": iso_utc(),
        },
    )


@app.post(
    "/notifications",
    response_model=NotificationLog,
    status_code=status.HTTP_201_CREATED,
    tags=["notifications"],
    dependencies=[Depends(verify_bearer_token)],
    responses=PROBLEM_RESPONSES,
)
def send_notification(response: Response, payload: NotificationEventRequest = Body(...)) -> NotificationLog:
    record, duplicate = store.process(payload, origin="rest")
    if duplicate:
        raise ProblemException(
            409, "duplicate-event", "Trùng lặp sự kiện thông báo",
            f"Sự kiện có event_id {payload.event_id} đã được xử lý trước đó (notification_id {record['notification_id']})",
        )
    response.headers["Location"] = f"/notifications/{record['notification_id']}"
    return NotificationLog(**record)


@app.get(
    "/notifications",
    response_model=NotificationPage,
    tags=["notifications"],
    dependencies=[Depends(verify_bearer_token)],
    responses=PROBLEM_RESPONSES,
)
def list_notifications(
    cursor: Optional[str] = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    alert_id: Optional[str] = Query(default=None, pattern=ALERT_ID_PATTERN),
    status_filter: Optional[DeliveryStatus] = Query(default=None, alias="status"),
    channel: Optional[NotificationChannel] = Query(default=None),
) -> NotificationPage:
    try:
        page = store.page(
            limit=limit,
            cursor=cursor,
            alert_id=alert_id,
            status=status_filter.value if status_filter else None,
            channel=channel.value if channel else None,
        )
    except InvalidCursor as exc:
        raise ProblemException(400, "validation", "Dữ liệu không hợp lệ", str(exc))
    return NotificationPage(**page)


@app.get(
    "/notifications/recent",
    response_model=NotificationPage,
    tags=["notifications"],
    dependencies=[Depends(verify_bearer_token)],
    responses=PROBLEM_RESPONSES,
)
def recent_notifications(
    cursor: Optional[str] = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> NotificationPage:
    try:
        page = store.page(limit=limit, cursor=cursor)
    except InvalidCursor as exc:
        raise ProblemException(400, "validation", "Dữ liệu không hợp lệ", str(exc))
    return NotificationPage(**page)


def _not_found(notification_id: str) -> ProblemException:
    return ProblemException(
        404, "not-found", "Không tìm thấy tài nguyên",
        f"Không tồn tại thông báo với notification_id {notification_id}",
    )


@app.get(
    "/notifications/{notification_id}",
    response_model=NotificationLog,
    tags=["notifications"],
    dependencies=[Depends(verify_bearer_token)],
    responses=PROBLEM_RESPONSES,
)
def get_notification(notification_id: str) -> NotificationLog:
    record = store.get(notification_id)
    if record is None:
        raise _not_found(notification_id)
    return NotificationLog(**record)


@app.post(
    "/notifications/{notification_id}/retry",
    response_model=NotificationLog,
    tags=["notifications"],
    dependencies=[Depends(verify_bearer_token)],
    responses=PROBLEM_RESPONSES,
)
def retry_notification(notification_id: str) -> NotificationLog:
    try:
        record = store.manual_retry(notification_id)
    except RetryLimitReached as exc:
        raise ProblemException(409, "retry-limit-reached", "Đã vượt quá số lần retry", str(exc))
    if record is None:
        raise _not_found(notification_id)
    return NotificationLog(**record)

