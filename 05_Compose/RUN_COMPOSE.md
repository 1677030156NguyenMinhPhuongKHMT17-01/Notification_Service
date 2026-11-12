# RUN_COMPOSE.md – Hướng dẫn chạy Notification Service bằng Docker Compose (Lab 05)

Tài liệu này giúp bất kỳ ai (giảng viên, thành viên nhóm khác, hoặc máy chấm CI) clone repo sạch và khởi chạy toàn bộ stack 3 dịch vụ của **Notification Service (Nhóm 6)** bằng **Docker Compose**.

---

## Kiến trúc Stack (`docker-compose.yml`)

| Service | Container | Image / Build | Vai trò & Healthcheck |
|---|---|---|---|
| `db` | `fit4110-db-lab05` | `postgres:15-alpine` | Lưu bảng `notifications` bền vững qua volume `db-data` (`pg_isready`) |
| `mqtt-broker` | `fit4110-mqtt-lab05` | `eclipse-mosquitto:2` | Broker MQTT nội bộ (`campus.alerts`, `campus.alerts.dlq`) (`mosquitto_pub`) |
| `api` | `fit4110-api-lab05` | Build non-root `appuser` (`fit4110/notification-service:v0.1.0-team-notify`) | FastAPI REST fallback + Async MQTT subscriber (`/health`, `/ready`) |

Cả 3 service giao tiếp nội bộ qua mạng `team-internal` (bridge). `api` chỉ khởi động sau khi `db` và `mqtt-broker` đạt trạng thái `healthy`.

---

## 1. Clone repo & chuẩn bị cấu hình

```bash
git clone <repo-url>
cd FIT4110_<MSSV>/05_Compose
cp .env.example .env
```

*(Tùy chọn)* Cài dependencies cho Newman / Spectral:

```bash
npm install
```

---

## 2. Build & khởi chạy stack Docker Compose

```bash
docker compose up -d --build --wait
```

Kiểm tra trạng thái 3 container:

```bash
docker compose ps
```

---

## 3. Kiểm tra Readiness của từng dịch vụ

```bash
# 1. User non-root trong container API
docker compose exec -T api id

# 2. HTTP /health & /ready (xác nhận PostgreSQL + MQTT đã sẵn sàng)
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/ready

# 3. PostgreSQL readiness
docker compose exec -T db pg_isready -U lab05 -d notificationdb

# 4. MQTT Broker readiness
docker compose exec -T mqtt-broker mosquitto_pub -h 127.0.0.1 -p 1883 -t health/ping -m ok
```

---

## 4. Kiểm thử End-to-End (REST Newman + Async MQTT + PostgreSQL Persistence)

### 4.1. Chạy Newman trên stack Compose

```bash
npm run test:compose
```

Báo cáo JUnit XML và HTML Extra được xuất tại:

```text
reports/newman-lab05-compose.xml
reports/newman-lab05-compose.html
```

### 4.2. Kiểm thử luồng Async MQTT (`campus.alerts` → PostgreSQL → REST API)

Bắn một event `alert.created` thẳng vào Mosquitto Broker:

```bash
docker compose exec -T mqtt-broker mosquitto_pub -h 127.0.0.1 -p 1883 -t campus.alerts -m '{"event_id":"123e4567-e89b-12d3-a456-426614175501","event_name":"alert.created","correlationId":"req-mqtt-e2e-05","source":"core-business","alert_id":"ALT-501","severity":"critical","message":"Sự cố bất thường phát qua MQTT nội bộ Lab 05","target_channels":["telegram","email"],"timestamp":"2026-11-12T16:50:00Z"}'
```

Sau đó truy vấn lại qua REST API (kể cả sau khi `docker compose restart api`):

```bash
curl -H "Authorization: Bearer local-dev-token" "http://localhost:8000/notifications?alert_id=ALT-501"
```

---

## 5. Dừng stack & Plug-a-thon (Lab 06)

```bash
docker compose down        # giữ lại volume dữ liệu PostgreSQL
docker compose down -v     # xóa cả volume db-data
```

Khi kết nối với các nhóm khác trên mạng chung `class-net` ở Lab 06:

```bash
docker network create class-net || true
docker compose -f docker-compose.yml -f docker-compose.plugathon.yml up -d
```

