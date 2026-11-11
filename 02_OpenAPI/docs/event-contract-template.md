# Event Contract sơ bộ — Core Business → Notification Service (Cặp #4)

> File này ghi nhận thỏa thuận hợp đồng sự kiện đã chốt giữa **Core Business (Producer)** và **Notification Service — Nhóm 6 (Consumer)** cho **Dependency #4** trong Lab 02. Đặc tả AsyncAPI chi tiết chuyển sang Lab 03.

## 1. Thông tin dependency

- **Dependency số:** #4 (`Core Business → Notification Service`)
- **Producer:** Core Business Service
- **Consumer:** Notification Service (Nhóm 6)
- **Cơ chế:** Queue / Pub-Sub async (MQTT Broker lớp: `mqtt://192.168.1.51:1883` Anonymous / RabbitMQ)
- **Topic/Queue Subscribe:** `campus.alerts`
- **Các loại Event (`event_name`):** `alert.created`, `alert.escalated`, `alert.resolved`
- **Người ghi:** Nhóm Core Business + Nhóm 6 (Notification Service)
- **Ngày chốt:** 2026-08-27 (cập nhật đồng bộ thông số MQTT Broker & JSON `snake_case`)

---

## 2. Mục đích nghiệp vụ & Điều kiện phát sự kiện

Khi `Core Business Service` phát hiện sự kiện bất thường (từ IoT Ingestion, AI Vision hoặc Access Gate), Core tạo cảnh báo (`Alert`) và publish event bất đồng bộ lên topic `campus.alerts`. `Notification Service` subscribe vào topic này để gửi thông báo đa kênh (`telegram`, `email`, `discord`, `sms`) đến người phụ trách:

1. **`alert.created`:** Phát ngay khi một cảnh báo mới được khởi tạo trong Core Business → Notification gửi cảnh báo khẩn theo `target_channels` hoặc tự định tuyến theo `severity`.
2. **`alert.escalated`:** Phát khi cảnh báo vẫn ở trạng thái `OPEN` chưa được xác nhận/xử lý sau thời gian quy định → Notification gửi lại thông báo nhắc nhở với cấp độ leo thang (`escalation_level`).
3. **`alert.resolved`:** Phát khi sự cố đã được đội vận hành/bảo vệ xử lý xong → Notification gửi tin nhắn thông báo đóng cảnh báo kèm `resolution_note`.

---

## 3. Thông số kết nối Broker & Event Name / Topic

| Thành phần | Giá trị đã thống nhất |
|---|---|
| **Producer** | `Core Business Service` (`source: "core-business"`) |
| **Consumer** | `Notification Service` (Nhóm 6) |
| **MQTT Broker lớp** | `mqtt://192.168.1.51:1883` (Anonymous) |
| **Topic / Queue Subscribe** | `campus.alerts` |
| **Dead-Letter Topic / Queue** | `campus.alerts.dlq` |
| **Naming Convention** | **`snake_case`** cho các field của event, giữ nguyên **`correlationId`** để đồng bộ trace với Core Business |

| Event name (`event_name`) | Trigger tại Producer | Hành động tại Consumer (Notification Service) |
|---|---|---|
| `alert.created` | Cảnh báo mới được tạo | Kiểm tra idempotency (`event_id`), định tuyến kênh gửi và phát thông báo mới |
| `alert.escalated` | Cảnh báo quá hạn xử lý, tăng cấp độ leo thang | Gửi thông báo nhắc nhở/leo thang theo `escalation_level` |
| `alert.resolved` | Cảnh báo được đánh dấu đã giải quyết | Gửi thông báo xác nhận hoàn tất kèm `resolution_note` |

---

## 4. Payload Schema & Ví dụ JSON chuẩn (`snake_case`)

### 4.1. Bảng quy ước trường dữ liệu (Payload Schema)

| Field | Kiểu dữ liệu | Bắt buộc | Constraint / Ràng buộc | Mô tả |
|---|---|---|---|---|
| `event_id` | `string` (UUID) | ✅ Có (cả 3 event) | Format UUID v4/v7 | Mã định danh duy nhất của từng event, dùng làm **Idempotency Key**. |
| `event_name` | `string` (enum) | ✅ Có (cả 3 event) | `alert.created \| alert.escalated \| alert.resolved` | Tên loại sự kiện. |
| `correlationId` | `string` | ✅ Có (cả 3 event) | `minLength: 4`, `maxLength: 100` | Mã truy vết xuyên suốt từ sự kiện gốc (`req-...` hoặc UUID). |
| `source` | `string` | ✅ Có (cả 3 event) | `const: "core-business"` | Tên service phát sự kiện. |
| `alert_id` | `string` | ✅ Có (cả 3 event) | `pattern: ^ALT-[0-9]{3,6}$` | Mã định danh cảnh báo nghiệp vụ (ví dụ: `"ALT-001"`). |
| `timestamp` | `string` | ✅ Có (cả 3 event) | ISO 8601 `date-time` | Thời điểm phát sự kiện. |
| `severity` | `string` (enum) | ✅ Có (`alert.created`) | `low \| medium \| high \| critical` | Mức độ nghiêm trọng của cảnh báo (chữ thường). |
| `message` | `string` | ✅ Có (`alert.created`) | `minLength: 5`, `maxLength: 500` | Nội dung chi tiết cảnh báo cần gửi. |
| `target_channels` | `array<string>` | Tùy chọn | Phần tử thuộc `telegram \| email \| discord \| sms` | Danh sách kênh nhận. Nếu không truyền, Notification tự định tuyến theo `severity`. |
| `escalation_level` | `integer` | ✅ Có (`alert.escalated`) | `minimum: 1`, `maximum: 10` | Cấp độ leo thang hiện tại của cảnh báo. |
| `resolution_note` | `string` | ✅ Có (`alert.resolved`) | `minLength: 3`, `maxLength: 500` | Ghi chú kết quả xử lý khi đóng cảnh báo. |

### 4.2. JSON mẫu: `alert.created` (Đồng bộ theo thông số Core Business)

```json
{
  "event_id": "123e4567-e89b-12d3-a456-426614174000",
  "event_name": "alert.created",
  "correlationId": "req-0196fb3d-4ad7-7d1e-9f49-5d5148d2babc",
  "source": "core-business",
  "alert_id": "ALT-001",
  "severity": "high",
  "message": "Phát hiện sự cố an ninh khẩn cấp từ Core Business",
  "target_channels": ["telegram", "email", "sms"],
  "timestamp": "2026-08-27T15:30:00Z"
}
```

### 4.3. JSON mẫu: `alert.escalated`

```json
{
  "event_id": "123e4567-e89b-12d3-a456-426614174001",
  "event_name": "alert.escalated",
  "correlationId": "req-0196fb3d-4ad7-7d1e-9f49-5d5148d2babc",
  "source": "core-business",
  "alert_id": "ALT-001",
  "escalation_level": 2,
  "timestamp": "2026-08-13T08:40:00+07:00"
}
```

### 4.4. JSON mẫu: `alert.resolved`

```json
{
  "event_id": "123e4567-e89b-12d3-a456-426614174002",
  "event_name": "alert.resolved",
  "correlationId": "req-0196fb3d-4ad7-7d1e-9f49-5d5148d2babc",
  "source": "core-business",
  "alert_id": "ALT-001",
  "resolution_note": "Đội bảo vệ đã kiểm tra, là nhân viên IT quên thẻ.",
  "timestamp": "2026-08-13T09:00:00+07:00"
}
```

---

## 5. Error / Edge Cases & Delivery Concerns (Tối thiểu 5 tình huống theo Rubric B3)

| # | Tình huống lỗi / Edge Case | Nguyên nhân | Cách xử lý thống nhất tại Notification Service |
|---:|---|---|---|
| 1 | **Duplicate Event (Sự kiện bị gửi trùng)** | MQTT QoS 1 / Queue retry hoặc Producer publish lặp cùng một `event_id`. | Kiểm tra `event_id` trong bảng `notification_logs`. Nếu `event_id` đã tồn tại với trạng thái `delivered`, bỏ qua việc gửi lại và ghi nhận `duplicate_ignored`. |
| 2 | **Out-of-order Event (Sự kiện đến sai thứ tự)** | `alert.resolved` đến trước hoặc đồng thời với `alert.created` / `alert.escalated` của cùng `alert_id`. | So sánh `timestamp` của event mới với lịch sử của `alert_id`. Nếu `alert_id` đã có sự kiện `alert.resolved` với `timestamp` mới hơn, không gửi thông báo `alert.escalated` cũ nữa mà chỉ ghi log audit. |
| 3 | **Missing Required Field (Thiếu trường bắt buộc)** | Payload thiếu `event_id`, `alert_id`, `correlationId` hoặc `alert.created` thiếu `severity`/`message`. | Từ chối xử lý ngay (không retry vì lỗi dữ liệu vĩnh viễn), ghi log lỗi kèm `correlationId` và đẩy bản ghi lỗi sang Dead-Letter Topic/Queue (`campus.alerts.dlq`). |
| 4 | **Invalid Schema / Enum Mismatch (Sai kiểu dữ liệu hoặc enum)** | `severity` truyền giá trị lạ (ví dụ `"urgent"` thay vì `low/medium/high/critical`) hoặc `escalation_level` không phải số nguyên. | Validate bằng Pydantic / JSON Schema; nếu sai schema thì chuyển sang `campus.alerts.dlq` và ghi nhận `error_detail`. |
| 5 | **Downstream Channel Timeout / Error (Lỗi gửi Telegram/Email)** | Mất kết nối mạng tới Telegram API / SMTP hoặc bị rate-limit (`HTTP 429` / `5xx`). | Thực hiện **Retry tối đa 3 lần, mỗi lần cách nhau 5 giây (interval 5s)**. Nếu sau 3 lần vẫn thất bại, đánh dấu `status = "failed"`, lưu lý do vào `error_detail` và đẩy message vào Dead-Letter Queue (`campus.alerts.dlq`). |

---

## 6. Ràng buộc kỹ thuật đã chốt & Giao tiếp phụ (REST Sync Fallback)

| Vấn đề | Quyết định đã thống nhất |
|---|---|
| `event_id` bắt buộc | ✅ Có — UUID, dùng làm idempotency key |
| `event_name` bắt buộc | ✅ Có (`alert.created`, `alert.escalated`, `alert.resolved`) |
| `correlationId` bắt buộc | ✅ Có — để trace xuyên service |
| `source` bắt buộc | ✅ Có — `core-business` |
| `timestamp` bắt buộc | ✅ Có — ISO 8601 |
| `severity` enum | `low`, `medium`, `high`, `critical` |
| Notification tự định tuyến kênh? | ✅ Có — dựa trên `severity`; `target_channels` là tùy chọn |
| Kênh hỗ trợ | `telegram`, `email`, `discord`, `sms` |
| Event có thể gửi trùng | Có — Notification idempotent theo `event_id` |
| Retry khi lỗi | **3 lần, interval 5s** — chi tiết Lab 03 |
| Dead-letter queue | **Có** (`campus.alerts.dlq`) — chi tiết Lab 03 |
| Error response REST | Problem Details RFC 9457 (`application/problem+json`) |
| Field `error_detail` nullable | Dùng `type: [string, "null"]` (OpenAPI 3.1 chuẩn) |

### Giao tiếp phụ (REST Sync Fallback trong `openapi.yaml`):
- `POST /notifications`: Gửi thông báo thủ công (fallback/test).
- `GET /notifications`: Lấy log thông báo đã gửi (cho Analytics/Admin, hỗ trợ cursor-based pagination).
- `GET /notifications/recent`: Lấy nhanh các thông báo gần đây.
- `GET /notifications/{notification_id}`: Xem chi tiết trạng thái gửi và `error_detail`.
- `GET /health`: Kiểm tra trạng thái sống của service.

---

## 7. Issue chuyển sang Lab 03

1. Đặc tả AsyncAPI đầy đủ cho topic `campus.alerts` trên MQTT Broker `mqtt://192.168.1.51:1883`.
2. Kiểm thử thực tế cơ chế retry (3 lần, interval 5s) và Dead-Letter Queue (`campus.alerts.dlq`).
3. Kiểm thử tự động Schema Validation cho cả 3 loại message trên queue và trên REST fallback bằng Postman/Newman.
4. Phối hợp với nhóm Core Business kiểm thử luồng Escalation policy (sau bao lâu chưa xử lý thì Core phát `alert.escalated`).
