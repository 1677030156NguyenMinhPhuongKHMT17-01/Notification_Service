# Checklist Tham Gia & Vận Hành Plug-a-thon — Notification Service (Nhóm 6)

Danh sách kiểm tra phục vụ chuẩn bị trước buổi ghép mạng **Plug-a-thon**, vận hành trong buổi ghép nối liên nhóm và ghi nhận minh chứng sau phiên chạy.

> **Quy ước trạng thái trung thực:** `[x]` là hạng mục đã kiểm chứng xong (bao gồm kiểm tra tĩnh & chạy trực tiếp Docker Compose / E2E / Newman ngày `2026-11-13`); `[ ]` là hạng mục **chờ thực hiện trực tiếp tại buổi ghép mạng LAN Plug-a-thon của lớp học**.

---

## Phần A — Chuẩn bị trước Plug-a-thon (Contract & Repo Readiness)

- [x] **A1. Đóng băng hợp đồng Pair 04:** Bộ 9 tệp hợp đồng nằm tại `contracts/` (`notification.openapi.yaml` v1.0.0, `core-business.openapi.yaml` v1.0.0 read-only, `event-contract.md`, `producer-consumer-handshake.md`, `event-test-matrix.md`, 4 tệp Draft 2020-12 JSON Schema).
- [x] **A2. Parity & OpenAPI Lint tĩnh:** `python scripts/verify_frozen_contracts.py` kiểm chứng 9/9 tệp khớp SHA-256 với Lab 03 & Lab 05; `npm run lint:openapi` đạt `0 errors`.
- [x] **A3. Tách biệt cấu hình & zero-secret:** `.env.example` chỉ chứa giá trị dev an toàn (`AUTH_TOKEN=plugathon-dev-token`, `MQTT_BROKER_URL=mqtt://mqtt-broker:1883`, webhook rỗng); `.env`, `node_modules/`, `__pycache__/` bị `.gitignore` chặn commit.
- [x] **A4. Hỗ trợ Dual-Mode Compose:** Đã cấu hình cả chế độ standalone (`docker-compose.yml`) và chế độ ghép broker chung (`docker-compose.external-broker.yml` dùng `external: true` network `class-net`, network alias `notification-service`, tắt `mqtt-broker` nội bộ qua `profiles: ["local-broker"]`).
- [x] **A5. Bộ công cụ giả lập & tự động hóa sẵn sàng:** `scripts/core_business_simulator.py`, `scripts/run_plugathon_e2e.py`, `postman/FIT4110_lab06_plugathon.postman_collection.json` (21 req / 37 assertions) và `Makefile` hoàn chỉnh.

---

## Phần B — Kiểm chứng Local Standalone Stack (Live Runtime Verification — `2026-11-13`)

- [x] **B1. Build & Up thành công:** `docker compose up -d --build --wait` và `pwsh -File ../demo/run_demo.ps1` (`40.9s` ≤ 300s) khởi động sạch 3 container (`fit4110-api-lab06`, `fit4110-db-lab06`, `fit4110-mqtt-lab06`) ở trạng thái `healthy` ([compose-ps.txt](../evidence/logs/compose-ps.txt)).
- [x] **B2. Non-root & Probes:** `docker compose exec -T api id` xác nhận `uid=10001(appuser)`; `GET /health` và `GET /ready` đều trả HTTP `200` (`database.ready=true`, `mqtt.connected=true` — [health-ready.json](../evidence/logs/health-ready.json)).
- [x] **B3. Pair-04 End-to-End & Fault Recovery (`--with-compose-dlq-recovery`):** Tất cả `13/13` checks PASS, bao gồm `high → discord`, `Q05` duplicate MQTT, `Q09` `SUPPRESSED_OUT_OF_ORDER`, `SCHEMA_VALIDATION_FAILED` vào DLQ, tiêm lỗi `FAIL_CHANNELS=sms` vào DLQ `MAX_RETRIES_EXCEEDED` và phục hồi `delivered` (`retry_count=1`) qua `POST /notifications/{id}/retry` ([plugathon-e2e.log](../evidence/logs/plugathon-e2e.log)).
- [x] **B4. Newman Collection:** `npm run test:plugathon` chạy `21/21` requests / `37/37` assertions đạt `0` failures (`2.3s`) và xuất `reports/newman-plugathon.{html,xml}` ([newman-plugathon.html](../reports/newman-plugathon.html)).
- [x] **B5. Lưu log, ảnh chụp & nhật ký sự cố:** Đã thu đủ 6 log trong `evidence/logs/`, 3 screenshot (`swagger-ui.png`, `ready-endpoint.png`, `newman-report.png`) và biên bản [evidence/fault_record.md](../evidence/fault_record.md) ([evidence/README.md](../evidence/README.md)).

---

## Phần C — Ghép mạng Plug-a-thon với Nhóm Đối tác (`Core Business — Nhóm 5`)

- [ ] **C1. Kết nối `class-net` & Broker chung:** Tạo `docker network create class-net` và chạy `MQTT_BROKER_URL=mqtt://<BROKER_IP>:1883 docker compose -f docker-compose.yml -f docker-compose.external-broker.yml up -d --build --wait`; kiểm tra `GET /ready` trả `mqtt.connected: true`. *(Thực hiện tại phiên Plug-a-thon lớp học)*
- [ ] **C2. Handshake Pair 04 liên nhóm thật:** Nhận trực tiếp sự kiện `alert.created`, `alert.escalated`, `alert.resolved` do container/máy của **Nhóm 5 (Core Business)** phát ra, xác nhận xuất hiện bản ghi `status: "delivered"` tại `GET /notifications/recent` với đúng `correlationId`. *(Thực hiện tại phiên Plug-a-thon lớp học)*
- [ ] **C3. Kiểm tra Consumer khác (Analytics / Admin):** Xác nhận peer Consumer gọi được `GET http://notification-service:8000/notifications` hoặc `GET http://<HOST_IP>:8000/notifications/recent` kèm Bearer Token. *(Thực hiện tại phiên Plug-a-thon lớp học)*
- [ ] **C4. Kịch bản Demo 2–3 phút trên lớp:** Hoàn tất trình diễn trực tiếp 5 cảnh (Clean-Clone Start & Readiness → MQTT Happy Path → Schema-Invalid DLQ → Channel Fault & Manual Retry Recovery → Persistence Check) theo `../../demo/video_script_2_3min.md`.

