# Phân tích yêu cầu — Vai Provider (Notification Service & Core Business Event Producer)

- **Cặp đàm phán:** Pair #4 — Core Business ↔ Notification Service
- **Product:** Smart Campus Operations Platform (Nhóm 6 — Notification Service)
- **Provider service:**
  - Luồng REST Sync Fallback & Log Query: **Notification Service (Nhóm 6)** là REST API Provider.
  - Luồng Async Event (`campus.alerts`): **Core Business Service** là Event Producer phát sự kiện cho **Notification Service** xử lý.
- **Consumer service:** Core Business Service (gọi REST fallback / phát event) & Analytics/Admin (truy vấn log thông báo)
- **Người viết:** Nguyễn Minh Phượng – `<MãSinhViên>` (Nhóm 6 — Notification Service)
- **Ngày:** 2026-08-27

---

## 1. Resource & Event chính

| Resource / Event | Mô tả | Thuộc tính bắt buộc | Thuộc tính tùy chọn |
|---|---|---|---|
| `AlertCreatedEvent` (`alert.created`) | Sự kiện cảnh báo mới phát trên topic `campus.alerts` hoặc gửi qua `POST /notifications` | `event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `severity`, `message`, `timestamp` | `target_channels` (`telegram`, `email`, `discord`, `sms`) |
| `AlertEscalatedEvent` (`alert.escalated`) | Sự kiện leo thang cảnh báo khi quá hạn xử lý | `event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `escalation_level`, `timestamp` | `severity`, `message`, `target_channels` |
| `AlertResolvedEvent` (`alert.resolved`) | Sự kiện thông báo cảnh báo đã được giải quyết | `event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `resolution_note`, `timestamp` | `target_channels` |
| `NotificationLog` | Bản ghi trạng thái chuyển phát thông báo đa kênh | `notification_id`, `event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `channel`, `sent`, `status`, `retry_count`, `error_detail`, `created_at`, `delivered_at` | `severity`, `message`, `target_channels` |

---

## 2. Action / API & Topic dự kiến

| Cơ chế / Method | Path / Topic | Mục đích | Consumer gọi / nhận khi nào? |
|---|---|---|---|
| **MQTT Subscribe** | `campus.alerts` (`mqtt://192.168.1.51:1883`) | Nhận sự kiện `alert.created`, `alert.escalated`, `alert.resolved` bất đồng bộ | Ngay khi Core Business phát hiện bất thường, leo thang hoặc đóng cảnh báo |
| `GET` | `/health` | Kiểm tra trạng thái hoạt động của Notification Service và kết nối MQTT | Docker Healthcheck, API Gateway kiểm tra định kỳ |
| `POST` | `/notifications` | Gửi thông báo thủ công (REST sync fallback / test) | Khi cần test độc lập hoặc khi Core Business dùng kênh HTTP fallback |
| `GET` | `/notifications` | Lấy danh sách log thông báo đã gửi (cursor-based pagination) | Khi Analytics hoặc Admin cần tra cứu lịch sử gửi thông báo |
| `GET` | `/notifications/recent` | Lấy danh sách thông báo gần đây nhất | Khi Dashboard vận hành hiển thị các thông báo vừa phát |
| `GET` | `/notifications/{notification_id}` | Xem chi tiết trạng thái gửi, `retry_count` và `error_detail` của 1 thông báo | Khi cần kiểm tra kết quả chuyển phát của một thông báo cụ thể |

---

## 3. Error case (Tối thiểu 5 case)

| Status / Case | Tình huống | Response body / Hành vi dự kiến |
|---:|---|---|
| `400 Bad Request` | Payload sai định dạng JSON, thiếu trường bắt buộc (`event_id`, `event_name`, `alert_id`...) hoặc `event_name` không hợp lệ | `Problem` (`application/problem+json` theo chuẩn RFC 9457) |
| `401 Unauthorized` | Gọi REST API `/notifications` nhưng thiếu hoặc sai `Authorization: Bearer <token>` | `Problem` (`status: 401`, `title: "Chưa xác thực"`) |
| `404 Not Found` | Tra cứu `GET /notifications/{notification_id}` với UUID không tồn tại | `Problem` (`status: 404`, `title: "Không tìm thấy tài nguyên"`) |
| `409 Conflict` | Gửi trùng sự kiện có cùng `event_id` (vi phạm ràng buộc Idempotency) | `Problem` (`status: 409`, `title: "Trùng lặp sự kiện thông báo"`) |
| `422 Unprocessable Entity` | Đúng cú pháp JSON nhưng sai pattern `alert_id` (`^ALT-[0-9]{3,}$`) hoặc sai enum `severity` | `Problem` (`status: 422`, kèm mảng `errors` chỉ rõ `field`, `code`, `message`) |
| `500 / 503 & Retry / DLQ` | Kênh Telegram/Email/Discord bên ngoài bị lỗi kết nối, timeout hoặc DB/Service chưa sẵn sàng | Tự động retry **3 lần, interval 5s**; nếu vẫn lỗi thì ghi `error_detail` và đẩy vào DLQ (`campus.alerts.dlq`), hoặc trả `503` khi `/health` mất kết nối store |

---

## 4. Giả định bổ sung

- **Giả định 1:** MQTT Broker chung của lớp tại `mqtt://192.168.1.51:1883` cho phép kết nối Anonymous trong mạng LAN phòng lab; khi chạy độc lập ở máy cá nhân không nối LAN lớp, service có thể kết nối tới container `eclipse-mosquitto:2` local qua biến môi trường `MQTT_BROKER_URL`.
- **Giả định 2:** Nếu `Core Business` không truyền mảng `target_channels` trong sự kiện `alert.created` (hoặc `alert.escalated` / `alert.resolved`), `Notification Service` sẽ tự động định tuyến kênh gửi dựa trên `severity` (`low` → `email`; `medium` → `telegram`, `email`; `high` → `telegram`, `email`, `discord`; `critical` → `telegram`, `email`, `discord`, `sms`).
- **Giả định 3:** Trường `error_detail` trong bản ghi kết quả luôn tuân thủ chuẩn OpenAPI 3.1 union type `type: [string, "null"]` (bằng `null` khi gửi thành công).

---

## 5. Câu hỏi cho đối tác (Core Business)

1. Trong sự kiện `alert.created`, trường `severity` có luôn bắt buộc và dùng chữ thường (`low`, `medium`, `high`, `critical`) không?
2. `Core Business` muốn truyền cứng `target_channels` trong mọi event hay để `Notification Service` tự định tuyến khi `target_channels` vắng mặt?
3. Khi gửi thông báo ra Telegram/Email thất bại, việc retry sẽ do `Notification Service` tự thực hiện (3 lần, mỗi lần cách nhau 5s) hay thông qua cơ chế requeue của Broker?

---

## 6. Rủi ro tích hợp

| Rủi ro | Tác động | Đề xuất xử lý |
|---|---|---|
| Lệch quy ước đặt tên trường (`camelCase` vs `snake_case`) | Notification parse thiếu trường `alert_id`, `event_id`, `target_channels` | Chốt cứng convention `snake_case` cho toàn bộ payload, giữ nguyên `correlationId` theo mẫu JSON của Core Business |
| MQTT Broker gửi lặp message (QoS 1) | Người nhận bị spam nhiều tin nhắn Telegram giống hệt nhau | Sử dụng `event_id` (UUID) làm khoá Idempotency tại Notification Service |
| Kênh Telegram/SMTP bị nghẽn mạng | Làm chậm việc tiêu thụ các message tiếp theo trên topic `campus.alerts` | Xử lý gửi bất đồng bộ kèm cơ chế retry 3 lần (interval 5s) và chuyển sang Dead-Letter Queue nếu quá hạn |
