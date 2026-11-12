# Docker Compose Evidence – Lab 05 (Notification Service)

- **Nhóm:** Nhóm 6 (`team-notify`)
- **Stack:** `db` (`postgres:15-alpine`) + `mqtt-broker` (`eclipse-mosquitto:2`) + `api` (`fit4110/notification-service:v0.1.0-team-notify`)

---

## 1. Unit Tests & Compose Startup

- Docker `test` stage (`pytest -q tests`): **PASSED** ([`docker-test-stage.log`](./docker-test-stage.log)).
- `docker compose up -d --build --wait`: Cả 3 container `fit4110-db-lab05`, `fit4110-mqtt-lab05`, `fit4110-api-lab05` đạt trạng thái `healthy` đúng thứ tự `depends_on` ([`compose-up.log`](./compose-up.log), [`compose-ps.txt`](./compose-ps.txt)).

---

## 2. Readiness Checks (Non-root, DB, MQTT, `/health`, `/ready`)

Chi tiết log tại [`readiness-checks.log`](./readiness-checks.log):

- **Non-root user (`docker compose exec -T api id`):** `uid=10001(appuser) gid=10001(appgroup) groups=10001(appgroup)`
- **PostgreSQL (`pg_isready`):** `/var/run/postgresql:5432 - accepting connections`
- **MQTT Broker (`mosquitto_pub`):** `exit=0`
- **API `GET /health`:** `200 OK` (`"status":"ok"`, `"subscribed_topic":"campus.alerts"`)
- **API `GET /ready`:** `200 OK` (`"status":"ready"`, `"database":{"backend":"postgresql","ready":true}`, `"mqtt":{"enabled":true,"connected":true}`)

---

## 3. End-to-End Verification

1. **Async MQTT (`campus.alerts` → PostgreSQL → REST):** Bắn JSON `alert.created` (`ALT-501`) vào `mqtt-broker:1883`, `api` nhận bất đồng bộ qua `team-internal`, lưu vào PostgreSQL và truy vấn lại `200 OK` qua `GET /notifications?alert_id=ALT-501` ([`mqtt-e2e.log`](./mqtt-e2e.log)).
2. **Newman trên Compose stack (`npm run test:compose`):** **19/19 requests, 35/35 assertions PASS, 0 failures**, average `20ms` ([`newman-compose-cli.txt`](./newman-compose-cli.txt), [`../../reports/newman-lab05-compose.html`](../../reports/newman-lab05-compose.html), [`../../reports/newman-lab05-compose.xml`](../../reports/newman-lab05-compose.xml)).
3. **PostgreSQL Persistence sau restart:** Đếm trực tiếp trong PostgreSQL (`total_rows = 6`), chạy `docker compose restart api`, đợi `healthy` và truy vấn lại `ALT-501` thành công ([`db-persistence.log`](./db-persistence.log), [`compose-services.log`](./compose-services.log)).
