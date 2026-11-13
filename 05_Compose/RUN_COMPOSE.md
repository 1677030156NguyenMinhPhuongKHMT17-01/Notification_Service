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

# 3. PostgreSQL readiness (tự động đọc POSTGRES_USER & POSTGRES_DB trong container db)
docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

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

Hoặc dùng script demo có sẵn trong `scripts/` để test các kịch bản (`created`, `escalated`, `resolved`, `lifecycle`, `invalid-schema`, `ooo`) và theo dõi DLQ (`campus.alerts.dlq`):

```bash
# Terminal 1: Theo dõi campus.alerts.dlq
python scripts/mqtt_watch_dlq.py --timeout 20 --count 1

# Terminal 2: Bắn demo event hợp lệ và event lỗi schema
python scripts/mqtt_publish_demo.py --scenario created --alert-id ALT-501 --severity high
python scripts/mqtt_publish_demo.py --scenario invalid-schema
```

> Lưu ý: Kiểm thử Q09 out-of-order suppression sẽ giữ trạng thái `alert.resolved` của `ALT-001` (`2026-08-27T16:30:00Z`) trong volume `db-data`. Nếu muốn chạy lại `npm run test:compose` từ đầu, hãy dọn volume sạch bằng `docker compose down -v` trước khi khởi động lại.

---

## 5. Dừng stack & Plug-a-thon (Lab 06)

```bash
docker compose down        # giữ lại volume dữ liệu PostgreSQL
docker compose down -v     # xóa cả volume db-data
```

Khi kết nối với các nhóm khác trên mạng chung `class-net` ở Lab 06 (tham số hóa `MQTT_BROKER_URL` / `MQTT_CLIENT_ID`, gắn alias `notification-service`, và tránh xung đột cổng host `:1883`):

```bash
docker network create class-net || true
APP_PORT=8080 MQTT_BROKER_URL=mqtt://192.168.1.51:1883 \
  docker compose -f docker-compose.yml -f docker-compose.plugathon.yml up -d --build
```

