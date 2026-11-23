# syntax=docker/dockerfile:1.7
# FIT4110 Lab 05 – Notification Service (Nhóm 7)

ARG PYTHON_IMAGE=python:3.11-slim

############################
# 1) builder
############################
FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN python -m venv /opt/venv

COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


############################
# 2) test (optional target)
############################
FROM builder AS test

COPY requirements-dev.txt .
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements-dev.txt

WORKDIR /app
COPY src/ ./src/
COPY tests/ ./tests/
ENV PYTHONPATH=/app/src \
    MQTT_ENABLED=false \
    DATABASE_URL= \
    RETRY_INTERVAL_SECONDS=0.05
RUN /opt/venv/bin/python -m pytest -q tests


############################
# 3) runtime
############################
FROM ${PYTHON_IMAGE} AS runtime

LABEL org.opencontainers.image.title="fit4110-notification-service" \
      org.opencontainers.image.description="Smart Campus Notification Service (Nhóm 7) – Lab 05 Compose Stack" \
      org.opencontainers.image.version="0.5.0" \
      org.opencontainers.image.source="FIT4110_MSSV/05_Compose"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    SERVICE_NAME=notification-service \
    SERVICE_VERSION=0.5.0 \
    MQTT_ENABLED=true

WORKDIR /app

RUN groupadd --system --gid 10001 appgroup \
    && useradd --system --uid 10001 --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appgroup src/ ./src/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"APP_PORT\",\"8000\")}/health', timeout=3).read()" || exit 1

CMD ["sh", "-c", "exec uvicorn notification_app.main:app --app-dir src --host ${APP_HOST} --port ${APP_PORT} --proxy-headers"]

