# Event Contract — Pair 04: Core Business → Notification Service

> Bản hợp đồng chính thức (v1.0 Signed-off) giữa **Core Business (Event Producer)** và **Notification Service (Event Consumer)** cho Cặp phụ thuộc #4 trong Smart Campus Operations Platform.

---

## 1. Thông tin Dependency & Hạ tầng Broker

| Thành phần | Giá trị chốt |
|---|---|
| **Dependency Pair** | Pair 04 (`Core Business → Notification Service`) |
| **Event Producer** | Core Business Service (Nhóm 5) |
| **Event Consumer** | Notification Service (Nhóm 6) |
| **Cơ chế giao tiếp chính** | Queue / Pub-Sub Async |
| **MQTT Broker chung của lớp** | `mqtt://192.168.1.51:1883` (Anonymous) |
| **Topic chính (Subscribe)** | `campus.alerts` |
| **Dead-Letter Queue / Topic** | `campus.alerts.dlq` |
| **Các loại Event (`event_name`)** | `alert.created`, `alert.escalated`, `alert.resolved` |
| **Quy ước đặt tên trường** | `snake_case` phẳng (giữ `correlationId` để đồng bộ distributed tracing toàn hệ thống) |
| **Phiên bản hợp đồng** | `1.0` (Signed-off: 2026-08-13) |

---

## 2. Mục đích nghiệp vụ

Khi Core Business phát hiện sự kiện bất thường (từ IoT, Access Gate, AI Vision), Core Business tạo alert và publish event lên topic `campus.alerts`. Notification Service subscribe topic này để gửi thông báo đa kênh (`telegram`, `email`, `discord`, `sms`) đến người phụ trách:
- `alert.created`: Gửi cảnh báo mới theo `target_channels` hoặc tự động định tuyến theo `severity`.
- `alert.escalated`: Gửi lại cảnh báo với mức độ leo thang (`escalation_level`) khi chưa được xử lý sau thời gian quy định.
- `alert.resolved`: Gửi thông báo xác nhận sự cố đã được xử lý kèm `resolution_note`.

---

## 3. Payload chuẩn theo từng Event Type

### 3.1. `alert.created`

**Payload mẫu từ Core Business:**
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

**Bảng quy định các trường (`alert.created`):**

| Trường | Kiểu dữ liệu | Bắt buộc | Ràng buộc | Mô tả |
|---|---|---|---|---|
| `event_id` | `string` (`uuid`) | Có | UUID chuẩn | Định danh duy nhất của event, dùng làm **idempotency key** để chống gửi trùng |
| `event_name` | `string` | Có | `const: "alert.created"` | Tên loại sự kiện |
| `correlationId` | `string` | Có | `minLength: 1` | Mã vết xuyên suốt các service thuộc cùng một luồng nghiệp vụ |
| `source` | `string` | Có | `const: "core-business"` | Tên service phát sự kiện |
| `alert_id` | `string` | Có | `pattern: "^ALT-[0-9]{3,}$"` | Mã định danh cảnh báo nghiệp vụ |
| `severity` | `string` | Có | `enum: ["low", "medium", "high", "critical"]` | Mức độ nghiêm trọng của cảnh báo |
| `message` | `string` | Có | `minLength: 5, maxLength: 500` | Nội dung thông báo |
| `target_channels` | `array<string>` | Tùy chọn | `items.enum: ["telegram", "email", "discord", "sms"]`, `minItems: 1`, `uniqueItems: true` | Danh sách kênh đích; nếu vắng mặt, Notification tự định tuyến theo `severity` |
| `timestamp` | `string` (`date-time`) | Có | ISO 8601 `date-time` | Thời điểm phát sinh sự kiện |

---

### 3.2. `alert.escalated`

**Payload mẫu:**
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

**Bảng quy định các trường (`alert.escalated`):**

| Trường | Kiểu dữ liệu | Bắt buộc | Ràng buộc | Mô tả |
|---|---|---|---|---|
| `event_id` | `string` (`uuid`) | Có | UUID chuẩn | Idempotency key của sự kiện leo thang |
| `event_name` | `string` | Có | `const: "alert.escalated"` | Tên loại sự kiện |
| `correlationId` | `string` | Có | `minLength: 1` | Mã vết xuyên service |
| `source` | `string` | Có | `const: "core-business"` | Service phát sự kiện |
| `alert_id` | `string` | Có | `pattern: "^ALT-[0-9]{3,}$"` | Mã cảnh báo đang được leo thang |
| `escalation_level` | `integer` | Có | `minimum: 1, maximum: 5` | Cấp độ leo thang hiện tại |
| `severity` | `string` | Tùy chọn | `enum: ["low", "medium", "high", "critical"]` | Mức độ nghiêm trọng mới (nếu thay đổi khi leo thang) |
| `message` | `string` | Tùy chọn | `minLength: 5, maxLength: 500` | Nội dung bổ sung khi leo thang |
| `target_channels` | `array<string>` | Tùy chọn | `items.enum: ["telegram", "email", "discord", "sms"]` | Kênh ưu tiên gửi leo thang |
| `timestamp` | `string` (`date-time`) | Có | ISO 8601 `date-time` | Thời điểm leo thang |

---

### 3.3. `alert.resolved`

**Payload mẫu:**
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

**Bảng quy định các trường (`alert.resolved`):**

| Trường | Kiểu dữ liệu | Bắt buộc | Ràng buộc | Mô tả |
|---|---|---|---|---|
| `event_id` | `string` (`uuid`) | Có | UUID chuẩn | Idempotency key của sự kiện giải quyết |
| `event_name` | `string` | Có | `const: "alert.resolved"` | Tên loại sự kiện |
| `correlationId` | `string` | Có | `minLength: 1` | Mã vết xuyên service |
| `source` | `string` | Có | `const: "core-business"` | Service phát sự kiện |
| `alert_id` | `string` | Có | `pattern: "^ALT-[0-9]{3,}$"` | Mã cảnh báo đã được giải quyết |
| `resolution_note` | `string` | Có | `minLength: 3, maxLength: 500` | Ghi chú kết quả xử lý sự cố |
| `target_channels` | `array<string>` | Tùy chọn | `items.enum: ["telegram", "email", "discord", "sms"]` | Kênh thông báo hoàn tất |
| `timestamp` | `string` (`date-time`) | Có | ISO 8601 `date-time` | Thời điểm giải quyết |

---

## 4. Quy tắc Idempotency, Retry, DLQ, Versioning & Out-of-Order

1. **Idempotency & Deduplication (`Q05`):**
   - **Key chống trùng:** `event_id` (UUID).
   - **Quy tắc tại Consumer (Notification Service):** Lưu `event_id` đã xử lý vào bảng `processed_events` (TTL tối thiểu 24 giờ). Nếu nhận lại event có cùng `event_id`, Consumer ghi log `DUPLICATE_EVENT_SKIPPED`, ACK message ngay và **không gửi lại thông báo** ra Telegram/Email/SMS.
2. **Retry Policy (`Q06`):**
   - **Retry Owner:** Notification Service (Consumer).
   - **Chiến lược:** Khi gọi cổng gửi thông báo bên ngoài (Telegram Bot API / SMTP / SMS Gateway) gặp lỗi tạm thời (timeout, `429`, `5xx`), Consumer thực hiện retry tối đa **3 lần**, khoảng cách cố định **5 giây** (`interval = 5s`) cho mỗi kênh bị lỗi.
   - Nếu bản thân payload vi phạm JSON Schema (`Q02–Q04`), Consumer **không retry** mà từ chối ngay và đẩy thẳng vào DLQ kèm nguyên nhân lỗi schema.
3. **Dead-Letter Queue (`Q07`):**
   - **DLQ Topic/Queue:** `campus.alerts.dlq`
   - **Điều kiện chuyển DLQ:** Sau khi hết 3 lần retry vẫn thất bại hoàn toàn hoặc payload không hợp lệ theo JSON Schema. Message đưa vào `campus.alerts.dlq` đính kèm metadata `error_detail`, `failed_at`, `retry_count`.
4. **Quy tắc định tuyến kênh tự động theo `severity`:**
   - Khi `target_channels` không được truyền trong event, Notification Service tự động chọn kênh theo `severity`:
     - `low` → `["email"]`
     - `medium` → `["telegram", "email"]`
     - `high` → `["telegram", "email", "discord"]`
     - `critical` → `["telegram", "email", "discord", "sms"]`
5. **Versioning (`Q08`):**
   - Phiên bản hiện tại: `v1.0` (nhận diện qua tập `event_name` thuộc `["alert.created", "alert.escalated", "alert.resolved"]` và schema `additionalProperties: false`).
   - Bổ sung field optional mới là thay đổi tương thích ngược (`v1.x`); đổi tên field bắt buộc hoặc đổi kiểu dữ liệu là breaking change (`v2.0`) phải qua `negotiation-log.md`. Event có `event_name` lạ hoặc cấu trúc không tương thích sẽ bị từ chối ở bước Schema Validation và chuyển sang `campus.alerts.dlq`.
6. **Event đến trễ hoặc Out-of-Order (`Q09`):**
   - Nếu `alert.resolved` đến trước `alert.created` (do độ trễ mạng) cho cùng một `alert_id`: Consumer ghi nhận trạng thái `alert_id` đã `RESOLVED` theo `timestamp` mới hơn; khi `alert.created` có `timestamp` cũ hơn đến sau, Consumer vẫn lưu log audit nhưng gắn cờ `SUPPRESSED_OUT_OF_ORDER` để không phát cảnh báo khẩn cấp giả cho sự cố đã đóng.

