# Bằng chứng Kiểm thử & Xác minh Trực tiếp — Lab 06 Plug-a-thon (Nhóm 6)

Thư mục này lưu toàn bộ bằng chứng kiểm chứng chạy thực tế trên stack Docker Compose 3 container (`fit4110-api-lab06`, `fit4110-db-lab06`, `fit4110-mqtt-lab06`) ngày `2026-11-13`.

---

## 1. Bảng tổng hợp kết quả kiểm chứng thực tế

| Hạng mục kiểm chứng | Lệnh thực thi | Kết quả đo được | Tệp bằng chứng |
|---|---|---|---|
| **Frozen Contracts Parity** | `python scripts/verify_frozen_contracts.py` | **PASS (`9/9` tệp khớp SHA-256)** | [../../demo/demo_walkthrough.log](../../demo/demo_walkthrough.log) |
| **OpenAPI 3.1 Spectral Lint** | `npm run lint:openapi` | **PASS (`0` errors)** | [../../demo/demo_walkthrough.log](../../demo/demo_walkthrough.log) |
| **Compose Config Validation** | `docker compose config --quiet` (standalone + external overlay) | **PASS (`exit 0` cả 2 chế độ)** | [../../demo/demo_walkthrough.log](../../demo/demo_walkthrough.log) |
| **5-Minute Demo Walkthrough** | `pwsh -File demo/run_demo.ps1` | **PASS (`40.9s` ≤ 300s, `uid=10001`)** | [../../demo/demo_walkthrough.log](../../demo/demo_walkthrough.log) |
| **Automated E2E + DLQ Recovery** | `python scripts/run_plugathon_e2e.py --with-compose-dlq-recovery` | **PASS (`13/13` checks PASSED)** | [logs/plugathon-e2e.log](logs/plugathon-e2e.log) |
| **Pair-04 MQTT Handshake** | `python scripts/core_business_simulator.py --scenario lifecycle --alert-id ALT-601` | **PASS (`3/3` lifecycle events → Postgres)** | [logs/mqtt-handshake.log](logs/mqtt-handshake.log) |
| **Fault Injection & DLQ Recovery** | `SCHEMA_VALIDATION_FAILED`, `Q09`, `MAX_RETRIES_EXCEEDED` → `/retry`, `401/422/400/409` | **PASS (100% deterministic)** | [logs/dlq-fault.log](logs/dlq-fault.log), [fault_record.md](fault_record.md) |
| **Newman Integration Suite** | `npm run test:plugathon` | **PASS (`21/21` requests, `37/37` assertions, `0` failed, `2.3s`)** | [../reports/newman-plugathon.html](../reports/newman-plugathon.html), [../reports/newman-plugathon.xml](../reports/newman-plugathon.xml) |
| **Live Container & Probe State** | `docker compose ps -a`, `/health`, `/ready`, `logs api` | **PASS (`3/3` healthy, DB + MQTT connected)** | [logs/compose-ps.txt](logs/compose-ps.txt), [logs/health-ready.json](logs/health-ready.json), [logs/api-container.log](logs/api-container.log) |

---

## 2. Danh mục tệp bằng chứng

### 2.1. Logs thực tế (`evidence/logs/`)

- [compose-ps.txt](logs/compose-ps.txt) — Trạng thái `healthy` của 3 container, kiểm tra non-root `uid=10001(appuser)`, `pg_isready` và `mosquitto_pub`.
- [health-ready.json](logs/health-ready.json) — JSON trả về trực tiếp từ `GET /health`, `GET /ready` (`database.ready=true`, `mqtt.connected=true`) và `GET /notifications/recent`.
- [plugathon-e2e.log](logs/plugathon-e2e.log) — Toàn bộ kết quả `13/13 checks PASSED` kèm Diagnostic JSON Summary.
- [mqtt-handshake.log](logs/mqtt-handshake.log) — Kết nối Pair 04 qua Mosquitto (`ALT-601`, `correlationId=req-pair04-hs-4fe7c61e`): thông điệp thô trên `campus.alerts` và bản ghi `delivered` lưu trong PostgreSQL.
- [dlq-fault.log](logs/dlq-fault.log) — Log thô các kịch bản tiêm lỗi: `SCHEMA_VALIDATION_FAILED` (`campus.alerts.dlq`), `Q09` `SUPPRESSED_OUT_OF_ORDER` (`ALT-690`), `MAX_RETRIES_EXCEEDED` (`ALT-888`) → phục hồi HTTP `200` qua `/retry`, cùng payload RFC 9457 (`401`/`422`/`400`/`409`).
- [api-container.log](logs/api-container.log) — Nhật ký container `fit4110-api-lab06` ghi nhận startup, manual retry recovery và structured stdout channel delivery (`telegram`, `email`, `discord`, `sms`).

### 2.2. Ảnh chụp màn hình thực tế (`evidence/screenshots/`)

- [swagger-ui.png](screenshots/swagger-ui.png) — Giao diện Swagger UI sống tại `http://127.0.0.1:8000/docs` (OpenAPI 3.1.0 `v1.0.0`).
- [ready-endpoint.png](screenshots/ready-endpoint.png) — Trạng thái `/ready`, `/health`, `docker compose ps` và bảng dữ liệu thật từ `/notifications/recent`.
- [newman-report.png](screenshots/newman-report.png) — Báo cáo Newman Dashboard (`21` requests, `37` assertions, `0` failed).

### 2.3. Biên bản, Báo cáo, Video & Phản tư

- Biên bản tiêm lỗi & phục hồi: [fault_record.md](fault_record.md)
- Báo cáo Newman xuất tự động: [../reports/newman-plugathon.html](../reports/newman-plugathon.html) & [../reports/newman-plugathon.xml](../reports/newman-plugathon.xml)
- Walkthrough toàn trình Demo Pack 5 phút: [../../demo/demo_walkthrough.log](../../demo/demo_walkthrough.log)
- Liên kết & kịch bản quay video 2–3 phút: [demo_video_link.txt](demo_video_link.txt) & [../../demo/video_script_2_3min.md](../../demo/video_script_2_3min.md)
- Phản tư cá nhân: [reflection/individual_reflection.md](reflection/individual_reflection.md)
