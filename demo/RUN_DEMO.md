# RUN_DEMO.md — Hướng dẫn chạy Demo Pack trong 5 phút (Clean Clone)

Tài liệu này hướng dẫn tái lập toàn bộ kịch bản kiểm chứng **Notification Service (Nhóm 6 — Pair 04)** từ một bản `git clone` sạch trên **Windows (PowerShell)** hoặc **Linux / macOS / Git Bash (Bash)** trong vòng **≤ 5 phút**, không cần bất kỳ secret hay tài khoản ngoài nào.

---

## 0. Yêu cầu công cụ trên máy

| Công cụ | Phiên bản tối thiểu | Mục đích |
|---|---|---|
| **Git** | `2.x+` | Clone repository |
| **Docker Engine + Compose v2** | Docker `24+`, `docker compose` v2 | Build image non-root và chạy stack 3 service (`api` + `db` + `mqtt-broker`) |
| **Python** | `3.9+` (khuyến nghị `3.11+`) | Chạy `verify_frozen_contracts.py`, `core_business_simulator.py`, `run_plugathon_e2e.py` (không cần cài thêm pip package trên host) |
| **Node.js & npm** *(khuyến nghị)* | Node `18+` / `20+` | Chạy Spectral OpenAPI lint và Newman HTML/XML report |

> **Cấu hình không chứa secret:** Mặc định [`06_Plugathon/.env.example`](../06_Plugathon/.env.example) để trống `DISCORD_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` để dịch vụ chạy ở chế độ **structured stdout mock**. Toàn bộ token test cục bộ sử dụng `AUTH_TOKEN=plugathon-dev-token`.

---

## 1. Phương án A — Chạy tự động bằng 1 lệnh (`run_demo.ps1` / `run_demo.sh`)

### Trên Windows PowerShell

```powershell
git clone <URL_REPO_PORTFOLIO_FIT4110_MSSV>
cd FIT4110_<MãSinhViên>
.\demo\run_demo.ps1 -Clean
```

*(Nếu đang quay demo và muốn giữ container chạy để mở Swagger UI `http://localhost:8000/docs`, bỏ cờ `-Clean`, sau đó dọn bằng `docker compose -f 06_Plugathon/docker-compose.yml down -v`.)*

### Trên Linux / macOS / Git Bash

```bash
git clone <URL_REPO_PORTFOLIO_FIT4110_MSSV>
cd FIT4110_<MãSinhViên>
chmod +x ./demo/run_demo.sh
./demo/run_demo.sh --clean
```

### Các bước script tự động thực hiện

1. **Tạo `.env` tạm thời:** Sao chép `06_Plugathon/.env.example` sang `06_Plugathon/.env` nếu chưa có; luôn tự động xóa `.env` tạm trong khối cleanup khi thoát (kể cả khi gặp lỗi).
2. **Kiểm tra frozen contracts (`verify_frozen_contracts.py`):** Xác nhận `9/9` tệp trong [`06_Plugathon/contracts/`](../06_Plugathon/contracts/) khớp byte-for-byte **SHA-256** với nguồn chuẩn Lab 03 & Lab 05 (`info.version: 1.0.0`).
3. **Kiểm tra cấu hình tĩnh:** `docker compose config --quiet` cho cả cấu hình standalone và overlay [`docker-compose.external-broker.yml`](../06_Plugathon/docker-compose.external-broker.yml); cài `npm ci` (nếu thiếu `node_modules`) và chạy `npm run lint:openapi`.
4. **Khởi động stack 3 service (`--wait`):** Build và chạy `api` (`uid=10001(appuser)`), `db` (`postgres:15-alpine`), `mqtt-broker` (`eclipse-mosquitto:2`).
5. **Kiểm tra probe sống & sẵn sàng:** Gọi `GET /health` (`status: ok`) và `GET /ready` (`status: ready`, `database.ready=true`, `mqtt.connected=true`).
6. **Chạy Pair-04 E2E & Fault/Retry Recovery (`run_plugathon_e2e.py --with-compose-dlq-recovery`):**
   - Publish qua MQTT `campus.alerts`: `alert.created` (`high` → tự định tuyến gồm `discord`), `Q05` duplicate `event_id`, `alert.escalated` (optional `severity`/`message`), `alert.resolved` (custom `target_channels`).
   - Bơm lỗi schema-invalid → kiểm tra `campus.alerts.dlq` nhận `SCHEMA_VALIDATION_FAILED`.
   - Bơm sự kiện trễ `Q09` → kiểm tra `status=duplicate_ignored` + `SUPPRESSED_OUT_OF_ORDER`.
   - Kiểm tra lỗi REST: `409` (trùng `event_id`), `401` (sai token), `422` (kênh `zalo` không hợp lệ), `GET /notifications/{id}`, `POST /notifications/{id}/retry`.
   - Tạm tái tạo container `api` với `FAIL_CHANNELS=sms MAX_RETRIES=0` → bắn MQTT `sms` → ghi nhận `status=failed` và `MAX_RETRIES_EXCEEDED` trên `campus.alerts.dlq` → khôi phục env → gọi `POST /notifications/{id}/retry` thành công (`status=delivered`).
7. **Chạy Newman (`npm run test:plugathon`):** Thực thi `21` requests và xuất báo cáo tại [`newman-plugathon.html`](../06_Plugathon/reports/newman-plugathon.html) & [`newman-plugathon.xml`](../06_Plugathon/reports/newman-plugathon.xml).

### Tham số tùy chọn của script

| PowerShell (`run_demo.ps1`) | Bash (`run_demo.sh`) | Ý nghĩa |
|---|---|---|
| `-Clean` | `--clean` | Tự động chạy `docker compose down -v` sau khi hoàn thành hoặc khi lỗi |
| `-SkipBuild` | `--skip-build` | Bỏ `--build` nếu Docker image đã build sẵn |
| `-SkipNewman` | `--skip-newman` | Bỏ qua `npm ci`, Spectral lint và Newman |
| `-NoDlqRecovery` | `--no-dlq-recovery` | Bỏ qua bước tái tạo container tiêm lỗi `FAIL_CHANNELS=sms` |
| `-Port <PORT>` | `--port <PORT>` | Đổi cổng host (mặc định `8000`) khi cổng `8000` đang bận |
| `-Help` | `--help` | Hiển thị trợ giúp |

---

## 2. Phương án B — Chạy thủ công từng lệnh (dành cho kiểm tra tương tác hoặc Plug-a-thon LAN)

Di chuyển vào thư mục `06_Plugathon/`:

```bash
cd 06_Plugathon

# 1. Xác minh frozen contracts & OpenAPI lint
python scripts/verify_frozen_contracts.py
npm ci && npm run lint:openapi

# 2. Khởi chạy stack độc lập với cấu hình mẫu
cp .env.example .env
docker compose up -d --build --wait
docker compose ps
docker compose exec -T api id

# 3. Kiểm tra /health & /ready
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready

# 4. Giả lập Core Business bắn trọn bộ kịch bản Pair 04 lên campus.alerts
python scripts/core_business_simulator.py --scenario all --alert-id ALT-601 --ooo-alert-id ALT-690
curl -fsS -H "Authorization: Bearer plugathon-dev-token" "http://127.0.0.1:8000/notifications/recent?limit=10"

# 5. Chạy bộ E2E đầy đủ (bao gồm DLQ recovery) & Newman
python scripts/run_plugathon_e2e.py --with-compose-dlq-recovery
npm run test:plugathon

# 6. Dọn sạch khi xong
docker compose down -v
rm -f .env
```

### Chế độ kết nối Broker chung của lớp (External `class-net`)

Khi ghép nối thực tế với Core Business (Nhóm 5) trên mạng Docker dùng chung `class-net`:

```bash
docker network create class-net || true
cd 06_Plugathon
APP_PORT=8080 MQTT_BROKER_URL=mqtt://192.168.1.51:1883 \
  docker compose -f docker-compose.yml -f docker-compose.external-broker.yml up -d --build --wait
```

Xem chi tiết cấu hình external broker, xử lý sự cố và biến môi trường tại [`06_Plugathon/RUN_PLUGATHON.md`](../06_Plugathon/RUN_PLUGATHON.md) và [`06_Plugathon/docs/integration_notes.md`](../06_Plugathon/docs/integration_notes.md).

---

## 3. Tài liệu tham chiếu sau khi chạy

- Kết quả chạy mẫu được ghi nhận tại: [`demo_walkthrough.log`](./demo_walkthrough.log)
- Kịch bản tiêm lỗi & biên bản thực nghiệm: [`fault_injection_runbook.md`](../06_Plugathon/docs/fault_injection_runbook.md), [`fault_record.md`](../06_Plugathon/evidence/fault_record.md)
- Báo cáo kiểm thử & minh chứng ảnh chụp: [`06_Plugathon/reports/newman-plugathon.html`](../06_Plugathon/reports/newman-plugathon.html), [`06_Plugathon/evidence/README.md`](../06_Plugathon/evidence/README.md)
