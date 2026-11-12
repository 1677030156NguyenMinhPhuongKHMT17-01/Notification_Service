# Docker Readiness Checklist – Notification Service (Nhóm 6)

## Dockerfile

- [x] Có base image hợp lý (`python:3.11-slim` multi-stage `builder` / `test` / `runtime`).
- [x] Có `WORKDIR /app`.
- [x] Có copy dependency (`requirements.txt`) trước source (`src/`) để tận dụng Docker layer cache.
- [x] Có `EXPOSE 8000`.
- [x] Có `CMD` dạng `exec uvicorn ...` dùng `sh -c` để truyền `APP_HOST` và `APP_PORT`.
- [x] Có `HEALTHCHECK` gọi `http://127.0.0.1:8000/health`.
- [x] Có user non-root (`appuser`, `uid=10001`).
- [x] Không chứa secret thật (`.env.example` chỉ chứa token dev, không chứa Telegram/SMTP token thật).

## Runtime

- [x] Container chạy được (`fit4110-notify-lab04`, trạng thái `Up ... (healthy)`).
- [x] Port map đúng (`0.0.0.0:8000->8000/tcp`).
- [x] `/health` trả `200 OK`.
- [x] Log khởi động và access log có `correlationId` / `trace_id` rõ ràng qua stdout.
- [x] Cấu hình hoàn toàn qua ENV (`APP_HOST`, `APP_PORT`, `AUTH_TOKEN`, `MQTT_ENABLED`, `FAIL_CHANNELS`).

## Testing

- [x] Chạy unit test `pytest` ngay trong Docker `test` stage (`6 passed`).
- [x] Chạy lại Postman Collection kế thừa Lab 03 trực tiếp trên container (`18/18 requests`, `33/33 assertions PASS`).
- [x] Newman report sinh ra trong `reports/` (`newman-lab04-local.xml`, `newman-lab04-local.html`).
- [x] Functional test pass (`alert.created`, `alert.escalated`, `alert.resolved`, query list/recent/detail, manual retry).
- [x] Auth test pass trên container (`401` khi thiếu token và khi token sai).
- [x] Negative test pass (`422` ProblemDetails cho payload/channel lỗi, `404` khi không tìm thấy `notification_id`).
- [x] Boundary & Reliability test pass (tự định tuyến kênh khi bỏ trống `target_channels`, `limit=101` trả `400`, trùng `event_id` trả `409 Conflict`, độ trễ trung bình `6ms < 1000ms`).

## Evidence

- [x] Có log `docker build` (`evidence/buoi-04/docker-build.log`, `docker-test-stage.log`).
- [x] Có log `docker run`, `docker ps`, `id` non-root (`evidence/buoi-04/docker-run-health.log`, `docker-container.log`).
- [x] Có log `curl /health` (`evidence/buoi-04/curl-health.txt`).
- [x] Có Newman HTML/XML report (`reports/newman-lab04-local.html`, `reports/newman-lab04-local.xml`).
- [x] Có tag image đúng quy ước (`fit4110/notification-service:lab04`, `ID: 7370407fd292`, `276MB`).
