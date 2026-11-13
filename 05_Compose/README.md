# FIT4110 — Lab 05: Điều phối đa dịch vụ với Docker Compose (Notification Service – Nhóm 6)

**Học phần:** FIT4110 – Dịch vụ kết nối và Công nghệ nền tảng  
**Service:** **Notification Service** (Nhóm 6 — Smart Campus Operations Platform)  
**Cặp tích hợp:** **Pair 04 (`Core Business → Notification Service`)**  
**Image tag:** `fit4110/notification-service:v0.1.0-team-notify`

---

## 1. Kiến trúc Stack Docker Compose

Thay vì chạy một container API với dữ liệu in-memory như Lab 04, Lab 05 điều phối toàn bộ **3 container** qua [`docker-compose.yml`](./docker-compose.yml) trên mạng nội bộ `team-internal`:

```text
   Core Business / Tester
      ├── REST Fallback (:8000) ───────────┐
      └── MQTT topic campus.alerts (:1883) ┼──► [ mqtt-broker (eclipse-mosquitto:2) ]
                                           │               ▲
                                           ▼               │ paho-mqtt (QoS 1)
                                   [ api (FastAPI, appuser) ]
                                           │
                                           ▼ psycopg3
                                   [ db (postgres:15-alpine) ] ──► volume: db-data
```

- **Bền vững dữ liệu với PostgreSQL (`db`):** Bảng `notifications` lưu trạng thái chuyển phát và khóa `event_id UNIQUE`, đảm bảo idempotency (`409 Conflict`), chặn sự kiện trễ `Q09` (`SUPPRESSED_OUT_OF_ORDER`), phục hồi các bản ghi `retrying` còn sót khi khởi động, và cho phép operator retry thủ công bản ghi `failed` qua `POST /notifications/{id}/retry`.
- **Luồng bất đồng bộ thật với Mosquitto (`mqtt-broker`):** Module [`mqtt_consumer.py`](./src/notification_app/mqtt_consumer.py) kết nối `MQTT_BROKER_URL` (mặc định `mqtt://mqtt-broker:1883`), lắng nghe `campus.alerts` với bounded `ThreadPoolExecutor`, định tuyến kênh theo `SEVERITY_ROUTING` (`low` → `email`; `medium` → `telegram, email`; `high` → `telegram, email, discord`; `critical` → `telegram, email, discord, sms`), và đẩy payload lỗi (`SCHEMA_VALIDATION_FAILED` / `MAX_RETRIES_EXCEEDED`) sang `campus.alerts.dlq`.
- **Readiness hoàn chỉnh:** `api` phụ thuộc `db` (`pg_isready`) và `mqtt-broker` (`mosquitto_pub`) qua `depends_on: condition: service_healthy`; endpoint `GET /health` kiểm tra sống + DB ping (`200` / `503`), endpoint `GET /ready` báo cáo trạng thái chi tiết của PostgreSQL và MQTT.

---

## 2. Kết quả kiểm chứng End-to-End

| Hạng mục | Lệnh / Kịch bản | Kết quả thực tế | Minh chứng |
|---|---|---|---|
| **Compose Syntax & OpenAPI Lint** | `docker compose config --quiet` & `npm run lint:openapi` | **PASS (0 errors)** | [`docker-compose.yml`](./docker-compose.yml), [`contracts/notification.openapi.yaml`](./contracts/notification.openapi.yaml) |
| **Unit Tests** | `docker build --target test` & `pytest -v tests` | **13/13 PASSED** (`13 passed, 1 warning in 0.60s`) | [`tests/test_api.py`](./tests/test_api.py), [`evidence/buoi-05/docker-test-stage.log`](./evidence/buoi-05/docker-test-stage.log) |
| **Stack Startup & Readiness** | `docker compose up -d --build --wait` | 3/3 container `healthy`, non-root `uid=10001(appuser)`, `/ready` trả `postgresql=ready` & `mqtt=connected` | [`evidence/buoi-05/compose-ps.txt`](./evidence/buoi-05/compose-ps.txt), [`readiness-checks.log`](./evidence/buoi-05/readiness-checks.log) |
| **Async MQTT E2E & DLQ** | `scripts/mqtt_publish_demo.py` & `scripts/mqtt_watch_dlq.py` (`ALT-501` / `ALT-502` / `ALT-520`) → Query REST | `ALT-501` (`high`) tự route `["telegram","email","discord"]` qua Mosquitto -> PostgreSQL (`200 OK`); `ALT-502` sai schema sang `campus.alerts.dlq`; `ALT-520` OOO bị chặn (`SUPPRESSED_OUT_OF_ORDER`) | [`scripts/mqtt_publish_demo.py`](./scripts/mqtt_publish_demo.py), [`scripts/mqtt_watch_dlq.py`](./scripts/mqtt_watch_dlq.py), [`evidence/buoi-05/mqtt-e2e.log`](./evidence/buoi-05/mqtt-e2e.log) |
| **Postman / Newman trên Compose** | `npm run test:compose` | **19/19 requests, 35/35 assertions PASS, 0 failures** (`2.1s`, avg `28ms`) | [`reports/newman-lab05-compose.html`](./reports/newman-lab05-compose.html), [`reports/newman-lab05-compose.xml`](./reports/newman-lab05-compose.xml) |
| **DB Persistence sau Restart** | `docker compose restart api` → Query lại `ALT-501` | Dữ liệu trong `notifications` (`total_rows = 8`) còn nguyên vẹn sau khi restart API | [`evidence/buoi-05/db-persistence.log`](./evidence/buoi-05/db-persistence.log) |

---

## 3. Tài liệu & Checklist

- Hướng dẫn chạy lại: [`RUN_COMPOSE.md`](./RUN_COMPOSE.md)
- Checklist readiness 6 điểm: [`checklists/readiness-checklist.md`](./checklists/readiness-checklist.md)
- Đóng góp nhóm & cá nhân: [`CONTRIBUTION.md`](./CONTRIBUTION.md)
- Vấn đề đã biết & giới hạn: [`known-issues.md`](./known-issues.md)
- CI Workflow kiểm tra Compose tự động: [`../.github/workflows/lab05-check.yml`](../.github/workflows/lab05-check.yml)
- File mở rộng cho Plug-a-thon (`class-net`, alias `notification-service`): [`docker-compose.plugathon.yml`](./docker-compose.plugathon.yml)
