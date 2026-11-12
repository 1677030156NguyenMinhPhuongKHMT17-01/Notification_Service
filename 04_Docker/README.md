# FIT4110 — Lab 04: Đóng gói Notification Service bằng Docker (Nhóm 6)

**Học phần:** FIT4110 – Dịch vụ kết nối và Công nghệ nền tảng  
**Service:** **Notification Service** (Nhóm 6 — Smart Campus Operations Platform)  
**Cặp tích hợp:** **Pair 04 (`Core Business → Notification Service`)**  
**Image tag:** `fit4110/notification-service:lab04`  

---

## 1. Kiến trúc & Điểm nổi bật

Dịch vụ **Notification Service** được hiện thực hóa bằng **Python 3.11 + FastAPI + Pydantic v2**, tái sử dụng trọn vẹn hợp đồng từ Lab 02 & Lab 03 ([`contracts/notification.openapi.yaml`](./contracts/notification.openapi.yaml)):

- **REST Sync Fallback & Log Query API:**
  - `GET /health` (public): dùng cho Docker `HEALTHCHECK` và monitoring (`mqtt_broker`, `subscribed_topic`).
  - `POST /notifications`: tiếp nhận 3 sự kiện `alert.created`, `alert.escalated`, `alert.resolved` (payload phẳng `snake_case`, giữ `correlationId`), idempotent theo `event_id` (trả `409 Conflict` khi trùng), tự định tuyến kênh theo `severity` nếu bỏ trống `target_channels`.
  - `GET /notifications` & `GET /notifications/recent`: phân trang cursor (`cursor`, `limit`), lọc theo `alert_id`, `status`, `channel`.
  - `GET /notifications/{notification_id}` & `POST /notifications/{notification_id}/retry`: xem log chuyển phát và gửi lại thủ công (tối đa 3 lần).
- **Xử lý lỗi chuẩn RFC 9457 (`application/problem+json`):** mọi lỗi `400`, `401`, `404`, `409`, `422`, `500` trả về đúng schema `Problem`.
- **Sẵn sàng cho luồng Async MQTT (`campus.alerts`):** module [`mqtt_consumer.py`](./src/notification_app/mqtt_consumer.py) đã tích hợp sẵn subscriber `paho-mqtt` và DLQ `campus.alerts.dlq` (mặc định `MQTT_ENABLED=false` ở Lab 04 để chạy độc lập, bật `true` ở Lab 05/06).
- **Dockerfile chuẩn Production:**
  - Multi-stage (`builder` → `test` → `runtime`) dựa trên `python:3.11-slim`.
  - Chạy dưới user non-root `appuser` (`uid=10001`).
  - Có `HEALTHCHECK` gọi `/health` và `.dockerignore` tối ưu build context.

---

## 2. Kết quả kiểm chứng trên Container thực tế

| Hạng mục kiểm thử | Lệnh thực thi | Kết quả thực tế | Minh chứng |
|---|---|---|---|
| **OpenAPI Lint** | `npm run lint:openapi` | **0 errors** | [`contracts/notification.openapi.yaml`](./contracts/notification.openapi.yaml) |
| **Unit Tests (Docker `test` stage)** | `docker build --target test -t fit4110/notification-service:test .` | **6/6 tests PASSED** (`pytest`) | [`evidence/buoi-04/docker-test-stage.log`](./evidence/buoi-04/docker-test-stage.log) |
| **Docker Build & Non-root Runtime** | `docker build -t fit4110/notification-service:lab04 .` | Image `276MB`, user `uid=10001(appuser)`, health `healthy` | [`evidence/buoi-04/docker-build.log`](./evidence/buoi-04/docker-build.log), [`docker-run-health.log`](./evidence/buoi-04/docker-run-health.log) |
| **Healthcheck HTTP** | `curl -s -i http://localhost:8000/health` | `200 OK` (`status: ok`) | [`evidence/buoi-04/curl-health.txt`](./evidence/buoi-04/curl-health.txt) |
| **Postman / Newman Docker Verification** | `npm run test:local` | **18/18 requests, 33/33 assertions PASS, 0 failures** (avg `6ms`) | [`reports/newman-lab04-local.html`](./reports/newman-lab04-local.html), [`reports/newman-lab04-local.xml`](./reports/newman-lab04-local.xml) |

> **Lưu ý:** Consumer-side Smoke Test gọi sang `Core Business Mock` (`TC15`) được lưu giữ đầy đủ tại `../03_Postman/`. Bộ Postman Lab 04 tập trung kiểm chứng trọn vẹn vòng đời container `notification-service` độc lập.

---

## 3. Cấu trúc thư mục `04_Docker/`

```text
04_Docker/
├── Dockerfile
├── .dockerignore
├── .env.example
├── Makefile
├── RUN_LOCAL.md
├── package.json
├── requirements.txt
├── requirements-dev.txt
├── contracts/
│   ├── notification.openapi.yaml
│   └── core-business.openapi.yaml
├── src/notification_app/
│   ├── config.py
│   ├── models.py
│   ├── delivery.py
│   ├── store.py
│   ├── mqtt_consumer.py
│   └── main.py
├── tests/
│   └── test_api.py
├── postman/
│   ├── collections/FIT4110_lab04_notification_docker.postman_collection.json
│   └── environments/
│       ├── FIT4110_lab04_local.postman_environment.json
│       └── FIT4110_lab04_mock.postman_environment.json
├── reports/
│   ├── newman-lab04-local.html
│   └── newman-lab04-local.xml
├── evidence/buoi-04/
│   ├── README.md
│   ├── docker-test-stage.log
│   ├── docker-build.log
│   ├── docker-run-health.log
│   ├── docker-images.txt
│   ├── curl-health.txt
│   ├── newman-local-cli.txt
│   └── docker-container.log
├── checklists/
└── .github/workflows/docker-newman.yml
```

Xem hướng dẫn chạy nhanh 4 bước tại [`RUN_LOCAL.md`](./RUN_LOCAL.md).
