# Team artefact and individual contribution (`CONTRIBUTION.md`)

File này ghi nhận phần đóng góp kỹ thuật và artefact chung của nhóm cho **Lab 05 (Docker Compose & Pair-04 Readiness)** theo chuẩn `FIT4110_Student_Kit`.

## Team information

- **Team:** Nhóm 6 *(hoặc A7 / B7)* — Phụ trách **Notification Service**
- **Service/capability:** **Notification Service** (Dịch vụ gửi cảnh báo đa kênh)
- **Dependency Pair:** **Pair #4: Core Business → Notification Service** (Async qua MQTT `campus.alerts` / `campus.alerts.dlq` + PostgreSQL + REST fallback `/notifications`)
- **Role:** Both (MQTT Event Consumer xử lý `alert.created`, `alert.escalated`, `alert.resolved` & DLQ; REST API Provider cho `/health`, `/ready`, `/notifications/*`)
- **Members:**
  - Nguyễn Minh Phượng – `<MãSinhViên>`
  - `<Thành viên 2>` – `<MSSV 2>`
  - `<Thành viên 3>` – `<MSSV 3>`
  - `<Thành viên 4>` – `<MSSV 4>`
- **Shared artefacts:**
  - `contracts/notification.openapi.yaml`
  - `docker-compose.yml` & `docker-compose.plugathon.yml`
  - `src/notification_app/{config,delivery,main,models,mqtt_consumer,store}.py`
  - `scripts/{_mqtt_compat.py,mqtt_publish_demo.py,mqtt_watch_dlq.py}`
  - `checklists/readiness-checklist.md` & `known-issues.md`

## Individual contribution

- **Work completed:**
  - Chuẩn hóa OpenAPI 3.1 (`contracts/notification.openapi.yaml`) và Pydantic models (`src/notification_app/models.py`) khớp với hợp đồng Pair-04 (`alert_id` `^ALT-[0-9]{3,}$`, `correlationId` `minLength: 1`, `escalation_level` `1..5`, optional `severity`/`message` trên `AlertEscalatedEvent`, optional `target_channels` trên `AlertResolvedEvent`, `NotificationLog.severity` nullable, bỏ giới hạn `retry_count <= 3`, bổ sung `503` cho `GET /health` và bỏ `403` dư trên `GET /notifications/recent`).
  - Hoàn thiện logic xử lý và lưu trữ bền vững PostgreSQL (`src/notification_app/store.py`): cập nhật `SEVERITY_ROUTING` bổ sung kênh `discord`, hỗ trợ field tùy chọn trong `_derive()`, gửi DLQ ngay khi `max_retries == 0`, chặn sự kiện trễ `Q09` (`SUPPRESSED_OUT_OF_ORDER` với `status=duplicate_ignored`), cho phép operator retry thủ công các bản ghi `failed` ở mọi `retry_count`, và phục hồi bản ghi `retrying` còn sót khi `init()`.
  - Tách xử lý bất đồng bộ MQTT sang `ThreadPoolExecutor` giới hạn luồng (`src/notification_app/mqtt_consumer.py`), chuẩn hóa envelope DLQ trên `campus.alerts.dlq` (`SCHEMA_VALIDATION_FAILED` / `MAX_RETRIES_EXCEEDED`), và bổ sung tùy chọn webhook Discord/Telegram bằng `urllib.request` trong `src/notification_app/delivery.py` (mặc định giữ mock stdout an toàn, kiểm tra `FAIL_CHANNELS` trước).
  - Parameterize `docker-compose.plugathon.yml` (`${MQTT_BROKER_URL:-mqtt://192.168.1.51:1883}`, `MQTT_CLIENT_ID`, alias `notification-service` trên `class-net`, tránh xung đột cổng `:1883`), sửa lệnh `pg_isready` trong `RUN_COMPOSE.md` & `Makefile`, và bổ sung script `scripts/mqtt_publish_demo.py` + `scripts/mqtt_watch_dlq.py` cùng unit tests trong `tests/test_api.py`.
- **Files or sections owned:**
  - `05_Compose/contracts/notification.openapi.yaml`
  - `05_Compose/src/notification_app/*`
  - `05_Compose/docker-compose.yml`, `05_Compose/docker-compose.plugathon.yml`, `05_Compose/.env.example`
  - `05_Compose/scripts/*`, `05_Compose/tests/test_api.py`
  - `05_Compose/{README.md,RUN_COMPOSE.md,Makefile,known-issues.md,CONTRIBUTION.md}`
- **Commands or tests run:**
  - `npm run lint:openapi`
  - `docker compose config --quiet` & `docker compose -f docker-compose.yml -f docker-compose.plugathon.yml config --quiet`
  - `docker build --target test -t fit4110/notification-service:test .`
  - `docker compose up -d --build --wait` & `npm run test:compose`
  - `python scripts/mqtt_watch_dlq.py` & `python scripts/mqtt_publish_demo.py`
- **Issues resolved:**
  - Khắc phục xung đột cổng `:1883` và tham số hóa broker/client ID khi ghép `docker-compose.plugathon.yml` trên mạng `class-net`.
  - Đồng bộ hoàn toàn quy tắc định tuyến kênh (`discord`), `Q09` out-of-order, `DLQ` envelope và manual retry trên bản ghi `failed` với bộ test Pair-04.
- **Remaining limitations:**
  - Chi tiết được ghi nhận đầy đủ trong [`known-issues.md`](./known-issues.md) (partner contract `core-business.openapi.yaml` read-only, chưa push image lên remote registry, kênh thực ở chế độ opt-in).
- **Corrections made after a deadline, if any:**
  - Đồng bộ hậu kiểm giữa `05_Compose` và hợp đồng chuẩn Pair-04 (`03_Postman/queue-contract-tests/pair-04-core-notification`).

## Agreement check

- [x] Shared artefacts match the agreed team version.
- [x] Personal contribution is described accurately.
- [x] No secret or private data is included.
