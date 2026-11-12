# Readiness Checklist – Lab 05 (Notification Service – Nhóm 6)

Danh sách kiểm tra readiness 6 điểm cho stack Docker Compose (`db` + `mqtt-broker` + `api`):

- [x] **Database ready:** Container `fit4110-db-lab05` (`postgres:15-alpine`) chạy ổn định, phản hồi `pg_isready -U lab05 -d notificationdb` (`accepting connections`), lưu bền vững bảng `notifications` trong volume `db-data` (kiểm chứng `total_rows = 6` và dữ liệu `ALT-501` còn nguyên vẹn sau `docker compose restart api`).
- [x] **MQTT Broker ready:** Container `fit4110-mqtt-lab05` (`eclipse-mosquitto:2`) mở cổng `1883` trong mạng `team-internal`, `mosquitto_pub` healthcheck `exit=0`, và tiếp nhận event `alert.created` trên topic `campus.alerts` để `api` xử lý bất đồng bộ end-to-end.
- [x] **API ready:** Container `fit4110-api-lab05` (`fit4110/notification-service:v0.1.0-team-notify`) chạy non-root `uid=10001(appuser)`, `/health` trả `200 OK`, `/ready` xác nhận `database.ready=true` & `mqtt.connected=true`, và Newman test pass **19/19 requests, 35/35 assertions (0 failures)**.
- [x] **Environment variables:** Cấu hình runtime được tách qua `.env.example` (`APP_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `AUTH_TOKEN`, `MQTT_ENABLED`, `MQTT_BROKER_URL`); không commit secret thật vào Git.
- [x] **Network & Ports:** Mạng `team-internal` (bridge) hoạt động, `api` kết nối nội bộ qua hostname `db:5432` và `mqtt-broker:1883`; các cổng `8000` (API), `5432` (PostgreSQL), `1883` (Mosquitto) map đúng; sẵn sàng gắn thêm `class-net` qua `docker-compose.plugathon.yml` cho Buổi 6.
- [x] **Image tags:** Image được build và gắn tag theo đúng quy ước `fit4110/notification-service:v0.1.0-team-notify` (non-root `appuser`, đã chạy unit test `pytest` ở Docker `test` stage).
