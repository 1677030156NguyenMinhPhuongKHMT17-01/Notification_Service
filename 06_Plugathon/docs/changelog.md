# Changelog — Notification Service (Nhóm 6 / A7 / B7)

Lịch sử tiến hóa hợp đồng, mã nguồn, hạ tầng và bộ kiểm thử của **Notification Service** qua 6 giai đoạn từ `01_Setup` đến `06_Plugathon` (tuân thủ **Luật 2 — Hợp đồng là luật & Quản lý thay đổi qua Changelog**).

---

## `[v1.0.0-plugathon]` — Lab 06: Plug-a-thon Integration & Demo Pack

### Cố định hợp đồng & Đồng bộ (Frozen Baseline)
- Khóa cứng **9 tệp hợp đồng** vào `FIT4110_MSSV/06_Plugathon/contracts/` và bổ sung `scripts/verify_frozen_contracts.py` kiểm tra đối chiếu **SHA-256** theo byte với nguồn chuẩn ở Lab 03 và Lab 05 (`9/9` trùng khớp).
- Giữ nguyên `notification.openapi.yaml` (`v1.0.0`, OpenAPI 3.1.0), `core-business.openapi.yaml` (`v1.0.0`, chỉ đọc phía Nhóm 6), `event-contract.md`, `producer-consumer-handshake.md`, `event-test-matrix.md` và 4 JSON Schema Draft 2020-12 (`alert.created`, `alert.escalated`, `alert.resolved`, `campus.alerts`).

### Hạ tầng Plug-a-thon & Tích hợp liên nhóm
- Thêm `docker-compose.yml` dùng build context `../05_Compose` (`Dockerfile` stage `runtime`, non-root `uid=10001:10001`), image `fit4110/notification-service:${IMAGE_TAG:-v1.0.0-plugathon}`, cùng `postgres:15-alpine` (`fit4110-db-lab06`) và `eclipse-mosquitto:2` (`fit4110-mqtt-lab06`).
- Thêm overlay `docker-compose.external-broker.yml` để ghép vào broker chung trong buổi Plug-a-thon: ẩn local `mqtt-broker` (`profiles: ["local-broker"]`, `ports: !override []`), gắn container `api` vào external network `class-net` với network alias `notification-service`, ghi đè `${MQTT_BROKER_URL:-mqtt://192.168.1.51:1883}`.
- Bổ sung `.env.example` cấu hình an toàn cho clean-clone (`ENV=plugathon`, `SERVICE_VERSION=1.0.0`, `AUTH_TOKEN=plugathon-dev-token`, không chứa credential/webhook thật).

### Công cụ kiểm thử, Giả lập & Tài liệu nộp bài
- Thêm `scripts/core_business_simulator.py` giả lập Producer Nhóm 5 cho đủ các kịch bản (`all`, `lifecycle`, `created`, `escalated`, `resolved`, `invalid-schema`, `ooo`).
- Thêm `scripts/run_plugathon_e2e.py` tự động hóa kiểm tra `/health`, `/ready`, Pair-04 MQTT lifecycle, `Q05` duplicate MQTT, `Q09` out-of-order, DLQ `SCHEMA_VALIDATION_FAILED`, lỗi REST (`409`/`401`/`422`), và chu trình `--with-compose-dlq-recovery` (`FAIL_CHANNELS=sms`, `MAX_RETRIES=0` → `campus.alerts.dlq` `MAX_RETRIES_EXCEEDED` → `POST /notifications/{id}/retry` phục hồi `delivered`).
- Thêm bộ Newman `postman/FIT4110_lab06_plugathon.postman_collection.json` (21 requests / 37 `pm.test` assertions) và workflow `.github/workflows/lab06-plugathon-demo.yml`.
- Hoàn thiện bộ tài liệu kiến trúc (`docs/`), sơ đồ chất lượng cao (`diagrams/`), slide trình bày (`slides/architecture_presentation.{html,pdf}`), runbook, checklist, `known-issues.md`, `CONTRIBUTION.md` và kịch bản Demo Pack (`../demo/`).

---

## `[v0.5.0]` — Lab 05: Multi-Service Docker Compose Stack (`05_Compose`)

- Đưa vào sử dụng bộ nhớ bền vững **PostgreSQL 15** (`PostgresBackend` trong `store.py`) cùng bảng `notifications`, ràng buộc `event_id UNIQUE`, `target_channels JSONB`, `event_timestamp` và cơ chế phục hồi bản ghi `retrying → failed` khi container khởi động lại (`init()`).
- Vận hành **Eclipse Mosquitto 2** thực thụ làm MQTT Broker nội bộ (`mqtt://mqtt-broker:1883`) kết hợp `MqttConsumer` (`paho-mqtt`, `clean_session=False`, QoS 1) và `ThreadPoolExecutor` (`MQTT_WORKER_THREADS=4`).
- Hỗ trợ cơ chế tiêm lỗi kênh tất định qua `FAIL_CHANNELS`, auto-retry `MAX_RETRIES=3` (`RETRY_INTERVAL_SECONDS=5`), publish DLQ hai lý do (`SCHEMA_VALIDATION_FAILED`, `MAX_RETRIES_EXCEEDED`) và opt-in gửi thật tới Discord/Telegram qua `urllib.request` (timeout `<= 5.0s`).
- Giữ `MemoryBackend` khi `DATABASE_URL` rỗng để chạy cô lập `pytest` (`13/13` pass) trong stage build Docker và thêm bộ kiểm thử Newman 19 requests / 35 assertions.

---

## `[v0.4.0]` — Lab 04: Dockerization & Non-Root Runtime (`04_Docker`)

- Đóng gói FastAPI service theo **multi-stage Dockerfile** (`python:3.11-slim`, user non-root `appuser` UID/GID `10001`), thêm `.dockerignore` tối ưu kích thước image.
- Bổ sung Docker `HEALTHCHECK` kiểm tra `/health`, tích hợp Newman chạy trực tiếp nhắm vào container đang chạy (18 requests / 33 assertions) và `13/13` unit tests `pytest`.

---

## `[v0.3.0]` — Lab 03: API Functional Testing, Newman & Pair-04 Queue Contract (`03_Postman`)

- Chốt bộ **Pair-04 Queue Contract** giữa Core Business (`Nhóm 5`) và Notification (`Nhóm 6`): topic `campus.alerts` và `campus.alerts.dlq`, ma trận test `Q01`–`Q09` (bao gồm `Q05` idempotency, `Q07` retry/DLQ, `Q08` bad JSON → DLQ, `Q09` `SUPPRESSED_OUT_OF_ORDER`).
- Phát hành 4 JSON Schema chuẩn Draft 2020-12 (`alert.created`, `alert.escalated`, `alert.resolved`, `campus.alerts`) với `additionalProperties: false`, regex `^ALT-[0-9]{3,}$`, `correlationId minLength=1`, `escalation_level 1..5`, và hỗ trợ trường optional trên `alert.escalated`/`alert.resolved`.
- Triển khai **mock server & test harness** đầu tiên kèm Postman collection kiểm thử chức năng, xác thực, dữ liệu âm tính và độ tin cậy.

---

## `[v0.2.0]` — Lab 02: OpenAPI Contract-First Design & Cross-Group Negotiation (`02_OpenAPI`)

- Đặc tả đầy đủ `notification.openapi.yaml` (`v1.0.0`, OpenAPI 3.1.0) theo chuẩn lỗi **RFC 9457** (`application/problem+json`), phân trang cursor trên `GET /notifications` và cơ chế Bearer Auth.
- Thực hiện thương lượng hợp đồng liên nhóm (`negotiation-log.md`, Issues `#1`–`#7`), đặc biệt **Issue #7** chốt đồng bộ:
  - Quy ước phẳng `snake_case` trên MQTT (giữ nguyên tên trường `correlationId`), không dùng envelope lồng nhau.
  - Chuẩn hóa `SEVERITY_ROUTING` với `high: ["telegram", "email", "discord"]` (bổ sung `discord` còn thiếu từ nháp Lab 01).
  - Loại bỏ nhầm lẫn `403` trên `/notifications/recent`, chuẩn hóa `400` cho query `limit > 100` và `422` cho lỗi Pydantic validation body, cho phép `NotificationLog.severity` nullable khi event đóng/leo thang không truyền `severity`.
- Đạt **0 errors** trên Spectral OpenAPI lint và mock-test với Prism.

---

## `[v0.1.0]` — Lab 01: Domain Modeling & Service Boundary (`01_Setup`)

- Khởi tạo workspace `FIT4110_MSSV`, xác định vai trò **Nhóm 6 *(hoặc A7 / B7)* — Notification Service** trong nền tảng **Smart Campus Operations Platform**.
- Thiết lập ranh giới sở hữu ban đầu: tách biệt với phần cứng IoT/Camera/AI Vision và Core Business; định hình danh sách endpoint REST, sự kiện MQTT Pair 04 và cấu trúc dữ liệu `notifications`.

