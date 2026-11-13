# Team artefact and individual contribution (`CONTRIBUTION.md`)

File này ghi nhận phần đóng góp cá nhân và artefact chung của nhóm cho **Lab 04 (Đóng gói Notification Service bằng Docker)** theo chuẩn `FIT4110_Student_Kit`.

## Team information

- **Team:** Nhóm 6 *(hoặc A7 / B7)* — Phụ trách **Notification Service**
- **Service/capability:** **Notification Service** (Dịch vụ gửi cảnh báo đa kênh)
- **Dependency Pair:** **Pair #4: Core Business → Notification Service** (Async MQTT `campus.alerts` / DLQ `campus.alerts.dlq` + REST fallback `/notifications`)
- **Role:** Both (Event Consumer cho `alert.created`, `alert.escalated`, `alert.resolved`; REST API Provider cho `/notifications`, `/health`)
- **Members:**
  - Nguyễn Minh Phượng – `<MãSinhViên>`
  - `<Thành viên 2>` – `<MSSV 2>`
  - `<Thành viên 3>` – `<MSSV 3>`
  - `<Thành viên 4>` – `<MSSV 4>`
- **Shared artefacts:**
  - `Dockerfile`, `.dockerignore`, `.env.example`, `Makefile`, `RUN_LOCAL.md`
  - `contracts/notification.openapi.yaml`
  - `src/notification_app/*` & `tests/test_api.py`
  - `postman/collections/FIT4110_lab04_notification_docker.postman_collection.json` & `postman/environments/*`
  - `checklists/docker_readiness_checklist.md`, `checklists/submission_checklist.md`, `known-issues.md`

## Individual contribution

- **Work completed:**
  - Đóng gói **Notification Service** (Python 3.11 + FastAPI + Pydantic v2 + `paho-mqtt`) bằng `Dockerfile` multi-stage (`builder` → `test` → `runtime`), chạy dưới user non-root `appuser` (`uid=10001`), có `HEALTHCHECK` gọi `/health` và cấu hình qua ENV (`.env.example`, giữ mặc định `MQTT_ENABLED=false` cho Lab 04 độc lập).
  - Đồng bộ `contracts/notification.openapi.yaml`, `models.py`, `store.py`, `mqtt_consumer.py` với hợp đồng chuẩn Pair 04 (`event-contract.md` và JSON Schema): hỗ trợ đầy đủ kênh `discord` trong `SEVERITY_ROUTING`, các trường tùy chọn trên `alert.escalated`/`alert.resolved`, chuẩn `^ALT-[0-9]{3,}$`, `correlationId` `minLength: 1`, `escalation_level` `1..5`, `NotificationLog.severity` nullable, `503` trên `/health`, bỏ `403` thừa trên `/notifications/recent`, xử lý `max_retries=0` -> DLQ, cho phép operator `manual_retry` bản ghi `failed`, chặn out-of-order `Q09 SUPPRESSED_OUT_OF_ORDER`, và offload `MqttConsumer._on_message` sang `ThreadPoolExecutor` với payload DLQ chuẩn.
  - Bổ sung unit tests trong `tests/test_api.py` và rà soát tài liệu (`README.md`, `checklists/*`, `known-issues.md`, `CONTRIBUTION.md`).
- **Files or sections owned:**
  - `04_Docker/contracts/notification.openapi.yaml`
  - `04_Docker/src/notification_app/*`
  - `04_Docker/tests/test_api.py`
  - `04_Docker/Dockerfile`, `04_Docker/README.md`, `04_Docker/RUN_LOCAL.md`, `04_Docker/checklists/*`, `04_Docker/known-issues.md`, `04_Docker/CONTRIBUTION.md`
- **Commands or tests run:**
  - `npm run lint:openapi`
  - `docker build --target test -t fit4110/notification-service:test .`
  - `docker build -t fit4110/notification-service:lab04 .`
  - `npm run test:local` & `npm run test:mock`
- **Issues resolved:**
  - Khắc phục drift hợp đồng giữa OpenAPI/code Lab 04 và bộ schema Pair 04 từ Lab 03.
  - Sửa bug `max_retries=0` bỏ qua DLQ, lỗi `manual_retry` bị chặn trên bản ghi `failed`, và bổ sung quy tắc `Q09` (`SUPPRESSED_OUT_OF_ORDER`).
  - Đồng bộ liên kết CI root (`../.github/workflows/lab04-docker-newman.yml`) và cập nhật số liệu trong checklist.
- **Remaining limitations:**
  - Image `fit4110/notification-service:lab04` và repo Git hiện ở trạng thái local-only (chưa push lên remote registry/GitHub); chi tiết xem tại `known-issues.md`.
- **Corrections made after a deadline, if any:**
  - Đồng bộ contract Pair 04, xử lý retry/DLQ/Q09 và bổ sung tài liệu checklist/known-issues/contribution trước khi kiểm chứng cuối.

## Agreement check

- [x] Shared artefacts match the agreed team version.
- [x] Personal contribution is described accurately.
- [x] No secret or private data is included.
