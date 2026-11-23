# RUN PLUGATHON — Hướng dẫn Chạy Lab 06 từ Clean Clone

Hướng dẫn từng bước để **chạy, kiểm chứng và ghép nối Plug-a-thon** cho **Notification Service (Nhóm 6 / A7 / B7)** trên máy mới vừa `git clone` mà **không** cần sửa mã nguồn hay lộ secrets.

---

## 1. Yêu cầu môi trường (Prerequisites)

- **Docker Engine / Docker Desktop** có **Docker Compose v2** (`docker compose version`).
- **Node.js 20+** & `npm` (cài Newman & Spectral CLI qua `package-lock.json`).
- **Python 3.11+** (các script kiểm thử dùng thư viện chuẩn Python — có sẵn fallback MQTT 3.1.1 trong `scripts/_mqtt_compat.py` nên host không bắt buộc cài `paho-mqtt`).
- **Git** & `curl` (hoặc PowerShell `Invoke-RestMethod` trên Windows).

---

## 2. Kiểm tra Hợp đồng & Cấu hình trước khi chạy (`Clean Clone Setup`)

Di chuyển vào thư mục Lab 06 và tạo `.env` từ mẫu an toàn:

```bash
cd FIT4110_MSSV/06_Plugathon
cp .env.example .env                 # Windows PowerShell: Copy-Item .env.example .env
```

Cài đặt CLI cục bộ và kiểm chứng tính toàn vẹn hợp đồng + Compose syntax:

```bash
npm ci                               # hoặc: make install
python scripts/verify_frozen_contracts.py   # Kiểm tra SHA-256 9/9 tệp đóng băng (make verify-contracts)
npm run lint:openapi                 # Spectral lint OpenAPI 3.1.0 -> 0 errors (make lint)
docker compose config --quiet        # Validate standalone compose (make config)
docker compose -f docker-compose.yml -f docker-compose.external-broker.yml config --quiet
```

> **Lưu ý an toàn (.env):** `.env.example` mặc định bật `MQTT_ENABLED=true`, `AUTH_TOKEN=plugathon-dev-token` và để trống `DISCORD_WEBHOOK_URL` / `TELEGRAM_BOT_TOKEN` nên chạy hoàn toàn an toàn ở chế độ **stdout mock**. Nếu muốn gửi tin nhắn ra kênh Discord/Telegram thật trong demo trực tiếp, tự điền biến tương ứng trong `.env` (file `.env` đã được `.gitignore` chặn commit).

---

## 3. Chế độ A — Chạy Standalone Stack cục bộ (3 Containers)

Khởi tạo PostgreSQL 15 (`fit4110-db-lab06`), Mosquitto 2 (`fit4110-mqtt-lab06`) và FastAPI (`fit4110-api-lab06`):

```bash
docker compose up -d --build --wait  # hoặc: make up
docker compose ps                    # hoặc: make ps
```

Kiểm tra quyền non-root và readiness probes:

```bash
docker compose exec -T api id        # Kỳ vọng: uid=10001(appuser) gid=10001(appuser)
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/ready
```

*(Hoặc chạy nhanh `make readiness` trên Linux/macOS/Git Bash).*

### Chạy Giả lập, E2E Tự động & Bộ Newman

1. **Giả lập Core Business gửi đủ kịch bản MQTT Pair 04:**
   ```bash
   python scripts/core_business_simulator.py --scenario all   # hoặc: make sim
   ```
   *(Hỗ trợ `--scenario {all,lifecycle,created,escalated,resolved,invalid-schema,ooo}`, `--alert-id ALT-601`, `--broker mqtt://127.0.0.1:1883`, `--json`).*

2. **Chạy toàn bộ E2E Suite + Tiêm lỗi DLQ & Manual Retry Recovery (`13` checks):**
   ```bash
   python scripts/run_plugathon_e2e.py --with-compose-dlq-recovery   # hoặc: make e2e
   ```
   Lệnh này tự động kiểm tra `/health`, `/ready`, Pair-04 lifecycle (`high → discord`), `Q05` duplicate MQTT, `Q09` `SUPPRESSED_OUT_OF_ORDER`, schema invalid → DLQ (`SCHEMA_VALIDATION_FAILED`), REST `409`/`401`/`422`, tạm recreate container `api` với `FAIL_CHANNELS=sms MAX_RETRIES=0` để xác nhận DLQ `MAX_RETRIES_EXCEEDED`, khôi phục ENV sạch và gọi `POST /notifications/{id}/retry` thành công (`status=delivered`).

3. **Chạy Postman / Newman Plug-a-thon Suite (21 requests / 37 assertions):**
   ```bash
   npm run test:plugathon               # hoặc: make test-plugathon
   ```
   Báo cáo được xuất ra `reports/newman-plugathon.html` và `reports/newman-plugathon.xml`.

---

## 4. Chế độ B — Ghép Plug-a-thon Mạng Chung (`class-net` + Broker Lớp)

Khi tích hợp trực tiếp cùng nhóm **Core Business (Nhóm 5 / A6 / B6)** qua shared Docker network `class-net` và MQTT Broker chung của lớp:

```bash
# 1. Tạo network dùng chung (bỏ qua nếu đã tồn tại trên host)
docker network create class-net

# 2. Khởi chạy overlay tắt local mqtt-broker và trỏ tới IP broker của lớp
MQTT_BROKER_URL=mqtt://192.168.1.51:1883 \
  docker compose -f docker-compose.yml -f docker-compose.external-broker.yml up -d --build --wait
```

*(Trên Windows PowerShell:)*

```powershell
$env:MQTT_BROKER_URL="mqtt://192.168.1.51:1883"
docker compose -f docker-compose.yml -f docker-compose.external-broker.yml up -d --build --wait
```

Kiểm tra kết nối thực tới broker lớp và chạy E2E nhắm thẳng vào broker chia sẻ:

```bash
curl -fsS http://localhost:8000/ready   # Xác nhận dependencies.mqtt.connected == true
python scripts/core_business_simulator.py --broker mqtt://192.168.1.51:1883 --scenario lifecycle
python scripts/run_plugathon_e2e.py --broker mqtt://192.168.1.51:1883
npm run test:plugathon
```

- **Địa chỉ service trên `class-net`:** Các container đối tác (Core Business, Analytics) gọi trực tiếp `http://notification-service:8000` (qua network alias khai báo trong `docker-compose.external-broker.yml`) hoặc `http://<HOST_IP>:${APP_PORT:-8000}` qua mạng LAN.

---

## 5. Dừng Stack & Dọn dẹp Môi trường

```bash
docker compose down                  # Dừng container, giữ lại Postgres volume plugathon-db-data (make down)
docker compose down -v               # Xóa sạch container, network và DB volume để reset từ đầu (make down-clean)
```

---

## 6. Xử lý sự cố thường gặp (Troubleshooting)

| Triệu chứng | Nguyên nhân phổ biến | Cách xử lý |
| :--- | :--- | :--- |
| `network class-net declared as external, but could not be found` | Chưa tạo bridge network `class-net` trước khi dùng file overlay | Chạy `docker network create class-net` rồi chạy lại `up -d`. |
| `Bind for 0.0.0.0:8000 / 5432 / 1883 failed: port is already allocated` | Stack Lab 04/05 cũ hoặc ứng dụng khác đang giữ cổng | Chạy `docker compose down` ở thư mục `04_Docker`/`05_Compose`, hoặc đổi `APP_PORT` / `POSTGRES_PORT` / `MQTT_PORT` trong `.env`. |
| `GET /ready` trả `503` với `mqtt.connected: false` | Sai `MQTT_BROKER_URL` hoặc broker lớp (`192.168.1.51:1883`) chưa mở/chưa chạy | Kiểm tra kết nối LAN/container tới IP broker, chỉnh `MQTT_BROKER_URL` ở `.env` hoặc biến môi trường rồi `up -d`. |
| Xác thực Postgres thất bại khi đổi `POSTGRES_PASSWORD` | Volume `plugathon-db-data` đã khởi tạo bằng mật khẩu cũ | Chạy `docker compose down -v && docker compose up -d --build --wait`. |
| Windows Git Bash chuyển đường dẫn lỗi mount hoặc ANSI | Chạy trên PowerShell bị khác biến môi trường | Dùng `Copy-Item .env.example .env` và `$env:MQTT_BROKER_URL=...` trên PowerShell; hoặc xem [../demo/run_demo.ps1](../demo/run_demo.ps1). |
