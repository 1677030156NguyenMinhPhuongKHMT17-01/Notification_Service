# RUN_LOCAL.md – Hướng dẫn chạy Notification Service bằng Docker (Lab 04)

Tài liệu này giúp bất kỳ ai (giảng viên, thành viên nhóm khác, hoặc máy chấm CI) clone repo sạch và chạy lại **Notification Service (Nhóm 6)** trong Docker container chỉ với **4 bước**.

---

## 1. Clone repo & vào thư mục Lab 04

```bash
git clone <repo-url>
cd FIT4110_<MSSV>/04_Docker
```

---

## 2. Cài dependencies cho công cụ kiểm thử (Newman / Spectral / Prism)

```bash
npm install
```

*(Tùy chọn) Kiểm tra hợp đồng OpenAPI trước khi đóng gói:*

```bash
npm run lint:openapi
```

---

## 3. Build Docker image

Chạy stage `test` (pytest unit tests) và build image `runtime` non-root:

```bash
docker build --target test -t fit4110/notification-service:test .
docker build -t fit4110/notification-service:lab04 .
```

---

## 4. Run container & Kiểm tra `/health`

```bash
docker run -d --rm \
  --name fit4110-notify-lab04 \
  -p 8000:8000 \
  --env-file .env.example \
  fit4110/notification-service:lab04
```

Kiểm tra container đang chạy non-root (`appuser`) và trả `/health` 200 OK:

```bash
curl http://localhost:8000/health
docker inspect --format '{{.Config.User}} | {{.State.Health.Status}}' fit4110-notify-lab04
```

Kết quả mong đợi từ `GET /health`:

```json
{
  "status": "ok",
  "service": "notification-service",
  "mqtt_broker": "mqtt://192.168.1.51:1883",
  "subscribed_topic": "campus.alerts",
  "time": "2026-11-12T16:10:00Z"
}
```

---

## 5. Chạy Newman test trực tiếp trên Docker container

```bash
npm run test:local
```

Báo cáo JUnit XML và HTML Extra được xuất ra tại:

```text
reports/newman-lab04-local.xml
reports/newman-lab04-local.html
```

---

## 6. Dừng container & Xem log

```bash
docker logs fit4110-notify-lab04
docker stop fit4110-notify-lab04
```

*(Hoặc dùng lệnh tắt trong `Makefile`: `make build`, `make run-detached`, `make health`, `make test-docker`, `make stop`.)*
