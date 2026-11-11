# Phân tích yêu cầu — Vai Consumer (Notification Service Subscribe `campus.alerts`)

- **Cặp đàm phán:** Pair #4 — Core Business → Notification Service
- **Product:** Smart Campus Operations Platform (Nhóm 6 — Notification Service)
- **Consumer service:** **Notification Service (Nhóm 6)** (Subscribe nhận event từ `Core Business` trên topic `campus.alerts`)
- **Provider / Producer service:** **Core Business Service** (Publish event cảnh báo lên MQTT Broker `mqtt://192.168.1.51:1883`)
- **Người viết:** Nguyễn Minh Phượng – `<MãSinhViên>` (Nhóm 6 — Notification Service)
- **Ngày:** 2026-08-27

---

## 1. Resource / Event Consumer cần nhận

| Event / Resource | Consumer (Notification) dùng để làm gì? | Field bắt buộc với Consumer | Field có thể tùy chọn |
|---|---|---|---|
| `alert.created` | Tạo và gửi thông báo cảnh báo mới tới đội bảo vệ/quản lý qua Telegram, Email, SMS | `event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `severity`, `message`, `timestamp` | `target_channels` (nếu thiếu thì tự định tuyến theo `severity`) |
| `alert.escalated` | Gửi thông báo nhắc nhở leo thang khi sự cố chưa được xử lý | `event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `escalation_level`, `timestamp` | `target_channels` |
| `alert.resolved` | Gửi thông báo xác nhận sự cố đã được giải quyết xong | `event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `resolution_note`, `timestamp` | — |

---

## 2. Kênh giao tiếp & API liên quan

| Cơ chế / Method | Topic / Path | Lúc nào nhận / gọi? | Kỳ vọng dữ liệu / Response |
|---|---|---|---|
| **MQTT Subscribe** | Topic `campus.alerts` tại `mqtt://192.168.1.51:1883` | Lắng nghe liên tục 24/7 khi Notification Service khởi chạy | JSON phẳng theo `snake_case` có đủ `event_id`, `event_name`, `correlationId`, `alert_id`, `timestamp` |
| `POST` (Fallback) | `/notifications` | Khi Core Business hoặc Tester gọi trực tiếp qua HTTP REST | `201 Created` trả về `NotificationLog` kèm header `Location` |
| `GET` | `/notifications` & `/notifications/recent` | Khi Analytics hoặc Admin cần lấy lịch sử thông báo | `200 OK` trả về `NotificationPage` (`items`, `next_cursor`, `has_more`) |

---

## 3. Error case Consumer cần xử lý (Tối thiểu 5 case)

| Tình huống / Status | Consumer (Notification) hiểu là gì? | Consumer sẽ xử lý thế nào? |
|---|---|---|
| **Duplicate `event_id`** (`409 Conflict`) | Sự kiện đã được nhận và xử lý trước đó | Kiểm tra bảng idempotency theo `event_id`; bỏ qua việc gửi lại để tránh spam tin nhắn |
| **Invalid JSON / Missing Field** (`400 Bad Request`) | Message trên `campus.alerts` bị hỏng hoặc thiếu trường bắt buộc | Ghi log lỗi kèm `correlationId`, không retry, chuyển bản ghi sang Dead-Letter Queue (`campus.alerts.dlq`) |
| **Invalid Enum / Pattern** (`422 Unprocessable Entity`) | `severity` không thuộc `low/medium/high/critical` hoặc `alert_id` sai định dạng | Từ chối xử lý hoặc áp dụng kênh fallback mặc định cho mức `high` nếu đang ở chế độ khẩn cấp, đồng thời cảnh báo lỗi schema |
| **Out-of-order Event** | Nhận `alert.escalated` sau khi `alert.resolved` của cùng `alert_id` đã hoàn tất | Đối chiếu `timestamp` và trạng thái của `alert_id`; bỏ qua thông báo leo thang cũ |
| **External Channel Failure** (`500` / Timeout) | Telegram Bot API hoặc SMTP Server không phản hồi | Thực hiện **retry 3 lần, mỗi lần cách nhau 5 giây (interval 5s)**; nếu vẫn lỗi thì lưu `error_detail` và đẩy vào DLQ |
| **Unauthorized REST Call** (`401 Unauthorized`) | Request gọi vào REST API thiếu Bearer token | Trả về `application/problem+json` với status `401` |

---

## 4. Giả định bổ sung

- **Giả định 1:** Mọi message do `Core Business` bắn lên topic `campus.alerts` đều được mã hóa UTF-8 dạng JSON phẳng (`snake_case`).
- **Giả định 2:** `event_id` là duy nhất cho từng lần phát sự kiện (ví dụ: cùng `alert_id: "ALT-001"` nhưng khi tạo mới sẽ có `event_id` khác với lúc `alert.escalated` và `alert.resolved`).
- **Giả định 3:** Thời gian `timestamp` luôn tuân thủ chuẩn ISO 8601 có múi giờ (`Z` hoặc `+07:00`).

---

## 5. Câu hỏi cho Provider / Producer (Core Business)

1. Khi cảnh báo chuyển sang `alert.escalated` hoặc `alert.resolved`, Core Business có gửi kèm lại `message` gốc hay chỉ gửi `alert_id` + `escalation_level` / `resolution_note`?
2. Định dạng của `correlationId` có bắt buộc theo tiền tố `req-<uuid>` như mẫu `"req-0196fb3d-4ad7-7d1e-9f49-5d5148d2babc"` hay chấp nhận mọi chuỗi khác rỗng?
3. Trên MQTT Broker `mqtt://192.168.1.51:1883`, Core Business publish với mức QoS mấy (QoS 0 hay QoS 1)?

---

## 6. Rủi ro tích hợp

| Rủi ro | Tác động | Đề xuất xử lý |
|---|---|---|
| Core Business gửi `severity` viết hoa (`HIGH`) trong khi Notification chờ chữ thường (`high`) | Lỗi validation enum ở Consumer | Thống nhất rõ trong hợp đồng `event-contract-04-core-notification.md` dùng chữ thường `low`, `medium`, `high`, `critical` (và Consumer hỗ trợ `.lower()` khi parse MQTT để tăng tính chịu lỗi) |
| Mất kết nối tạm thời tới MQTT Broker `192.168.1.51:1883` | Notification không nhận được sự kiện trong lúc mất mạng | Cấu hình `paho-mqtt` tự động reconnect và cung cấp thêm endpoint `POST /notifications` làm REST sync fallback |
