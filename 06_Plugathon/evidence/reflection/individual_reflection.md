# Đánh giá & Phản tư Cá nhân — Đồ án FIT4110 (Lab 01 → Lab 06 Plug-a-thon)

| Thông tin | Giá trị |
| :--- | :--- |
| **Môn học** | FIT4110 — Dịch vụ kết nối và Công nghệ nền tảng |
| **Họ và tên** | Nguyễn Minh Phượng |
| **Mã sinh viên** | `<MãSinhViên>` |
| **Nhóm / Dịch vụ** | **Nhóm 6 *(hoặc A7 / B7)* — Notification Service** |
| **Cặp tích hợp chính** | **Pair 04:** Core Business (`Nhóm 5 / A6 / B6`) → Notification Service (`Nhóm 6 / A7 / B7`) |

---

## 1. Điều gì đã làm việc tốt qua 6 giai đoạn (Lab 01 → Lab 06)

1. **Thiết kế contract trước khi code (Contract-First + Frozen Baseline):**
   - Việc thống nhất OpenAPI 3.1.0 (`notification.openapi.yaml` v1.0.0) ở Lab 02 và JSON Schema Draft 2020-12 (`alert.created`, `alert.escalated`, `alert.resolved`, `campus.alerts`) ở Lab 03 giúp hai nhóm Core Business và Notification Service hiểu chính xác cấu trúc thông điệp ngay từ đầu.
   - Đến Lab 06, bộ hợp đồng gồm 9 tệp được khóa nguyên vẹn tại `contracts/` và kiểm chứng tự động bằng SHA-256 (`scripts/verify_frozen_contracts.py` → 9/9 khớp tuyệt đối) kết hợp Spectral lint (`npm run lint:openapi`), tránh tình trạng sửa hợp đồng âm thầm giờ chót (tuân thủ Luật 2 & Luật 5).
2. **Tách biệt rõ Producer/Consumer qua MQTT & Hàng đợi lỗi DLQ:**
   - Core Business không phải chờ các kênh gửi thông báo bên ngoài (Telegram/Discord/Email/SMS) phản hồi mà chỉ publish QoS 1 lên `campus.alerts`.
   - Worker bất đồng bộ (`ThreadPoolExecutor`, `MQTT_WORKER_THREADS=4`) trên container tách biệt giúp callback `paho-mqtt` không bị block và xử lý song song tốt. Payload lỗi cú pháp/schema được chuyển thẳng sang `campus.alerts.dlq` với lý do `SCHEMA_VALIDATION_FAILED` (`retry_count=0`), còn lỗi kênh sau chu kỳ retry (`MAX_RETRIES=3`, `RETRY_INTERVAL_SECONDS=5`) được đưa vào DLQ với `MAX_RETRIES_EXCEEDED` và cho phép phục hồi qua `POST /notifications/{id}/retry`.
3. **Tính di động của Compose Stack & Chế độ Plug-a-thon LAN:**
   - Triển khai dual-mode chỉ bằng tệp overlay `docker-compose.external-broker.yml`: không sửa code Python khi chuyển từ broker Mosquitto nội bộ (`mqtt://mqtt-broker:1883`) sang broker dùng chung của lớp (`${MQTT_BROKER_URL}`, mặc định `mqtt://192.168.1.51:1883` trên external network `class-net` với alias `notification-service`), đáp ứng đúng Luật 3 (không hard-code IP/secret) và nguyên tắc cấu hình qua biến môi trường.

## 2. Những lỗi, va vấp kỹ thuật thực tế & Cách xử lý

1. **Lệch `SEVERITY_ROUTING` cho mức `high` (`discord`) và trường optional của `alert.escalated` (Lab 01 → Lab 03 → Lab 05):**
   - *Vấn đề:* Trong bản nháp Lab 01, bảng routing nháp chưa thống nhất hẳn với `event-contract.md` Lab 03 (`high` thiếu `discord`), còn một số ví dụ `alert.escalated` chưa thể hiện đủ các trường optional `severity`, `message`, `target_channels`.
   - *Khắc phục:* Rà soát và ghi rõ ở `02_OpenAPI/negotiation-log.md` (Issue #7), cập nhật `SEVERITY_ROUTING` trong `store.py` (`low: [email]`, `medium: [telegram, email]`, `high: [telegram, email, discord]`, `critical: [telegram, email, discord, sms]`) và hỗ trợ đủ các trường optional trên `AlertEscalatedEvent` và `AlertResolvedEvent`.
2. **Xung đột HTTP status code chuẩn lỗi (`400` vs `422` vs RFC 9457) và truy vấn phân trang (`limit=101`):**
   - *Vấn đề:* Trong các tài liệu thiết kế ban đầu còn lẫn `400 Bad Request` và `422 Unprocessable Entity` khi Pydantic validate body; bên cạnh đó endpoint `GET /notifications/recent` từng bị đặt vấn đề có cần `403` riêng hay không.
   - *Khắc phục:* Chuẩn hóa toàn bộ phản hồi lỗi theo RFC 9457 (`application/problem+json`): lỗi parse JSON hoặc vi phạm ràng buộc query (`limit > 100`) trả `400`, lỗi schema Pydantic body (như kênh không hợp lệ `zalo` hoặc `alert_id` sai regex `^ALT-[0-9]{3,}$`) trả `422`, trùng `event_id` trên REST trả `409`, và DB/ready fail trả `503`. Kiểm chứng cả trong `pytest` (13/13) lẫn Newman.
3. **Thứ tự sự kiện lệch thời gian qua mạng MQTT (`Q09 Out-of-Order`):**
   - *Vấn đề:* Khi mạng lag, `alert.created` có thể đến sau `alert.resolved` của cùng `alert_id`, gây nguy cơ gửi nhầm cảnh báo cho sự cố đã đóng.
   - *Khắc phục:* Lưu cột `event_timestamp` trong PostgreSQL và kiểm tra trước khi gửi: nếu đã có `alert.resolved` mới hơn cho cùng `alert_id`, ghi nhận bản ghi với `status=duplicate_ignored`, `error_detail=SUPPRESSED_OUT_OF_ORDER:...` và không phát thông báo ra kênh ngoài.
4. **Hàng rào an ninh dữ liệu & Chế độ Clean-Clone không lộ secret:**
   - *Vấn đề:* Nếu bắt buộc token Discord/Telegram thật để chạy kiểm thử sẽ làm CI và người đánh giá không thể chạy sau khi `git clone`.
   - *Khắc phục:* `delivery.py` chạy mặc định ở chế độ stdout mock có cấu trúc và chỉ kích hoạt `urllib.request` webhook thật (timeout tối đa 5s) khi các biến `DISCORD_WEBHOOK_URL` / `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` được truyền qua `.env` cục bộ. Đồng thời `.gitignore` chặn tuyệt đối `.env`, `node_modules/`, `__pycache__/`.

## 3. Bài học rút ra cho Làm việc nhóm & Tích hợp hệ thống phân tán

- **Contract phải có "chứng nhận sống" (Executable Contract Tests):** Tài liệu Markdown hay file YAML chỉ thực sự đáng tin khi được chạy kèm Spectral lint, JSON Schema validator, Newman collection và E2E script tự động trước mỗi lần ghép nối.
- **Tôn trọng ranh giới dịch vụ & Quyền sở hữu tài liệu (Luật 1 & Luật 2):** Khi phát hiện `core-business.openapi.yaml` còn sót ví dụ `service: lab02-contract-template` tại `/health`, nhóm không tự ý sửa file hợp đồng của đối tác mà ghi nhận minh bạch trong `known-issues.md` để trao đổi hai chiều.
- **Observability & Readiness là điều kiện tiên quyết khi ghép nhóm:** `/health` (liveness + kiểm tra DB) và `/ready` (chỉ trả `200` khi cả DB lẫn MQTT client đã kết nối broker) giúp Docker Compose và script tự động tránh lỗi race-condition khi khởi động hoặc tái tạo container lúc tiêm lỗi (`FAIL_CHANNELS=sms`).

## 4. Hướng cải tiến nếu tiếp tục phát triển

1. Bổ sung chữ ký xác thực hoặc TLS/username-password MQTT khi triển khai vượt phạm vi mạng LAN lớp học.
2. Triển khai adapter Email (SMTP/SES) và SMS thật tương tự Discord/Telegram webhook kèm circuit breaker per-channel.
3. Xuất metrics Prometheus (`/metrics`) cho độ trễ gửi theo từng kênh, tỷ lệ vào `campus.alerts.dlq` và số lần suppression `Q09`.

