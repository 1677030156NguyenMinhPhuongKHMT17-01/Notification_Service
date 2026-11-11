# Producer–Consumer Handshake — Pair 04 (Queue Async)

> Biên bản xác nhận kiểm thử hợp đồng Event (Event Contract Handshake) giữa **Core Business (Event Producer)** và **Notification Service (Event Consumer)** theo Mục 10 của `Lab03_Kiểm thử Queue-Async.pdf`.

---

## 1. Thông tin định danh Pair & Vai trò

- **Pair:** Pair 04 (`Core Business → Notification Service`)
- **Event Producer:** Nhóm 5 — Core Business Service (`source: "core-business"`)
- **Event Consumer:** Nhóm 6 — Notification Service
- **Hạ tầng đích (Lab 05 / Plug-a-thon):** MQTT Broker `mqtt://192.168.1.51:1883` (Anonymous) — Topic `campus.alerts`
- **Các Event Type đã kiểm tra:**
  1. `alert.created`
  2. `alert.escalated`
  3. `alert.resolved`

---

## 2. Schema Canonical & Phiên bản hiện tại

- **Phiên bản hợp đồng (`contractVersion`):** `1.0` (Signed-off: `2026-08-13`)
- **Chuẩn JSON Schema:** `https://json-schema.org/draft/2020-12/schema`
- **Danh sách file Schema canonical:**
  - `schema/alert.created.schema.json`
  - `schema/alert.escalated.schema.json`
  - `schema/alert.resolved.schema.json`
  - `schema/campus.alerts.schema.json` (Schema tổng hợp `oneOf` cho toàn bộ topic `campus.alerts`)
- **Cam kết quản lý Schema:** Bản Event Contract và Schema canonical được đồng bộ thống nhất giữa Producer (Core Business) và Consumer (Notification Service). Không bên nào tự ý sửa tên trường hoặc thêm trường ngoài hợp đồng (`additionalProperties: false`) mà không cập nhật biên bản thương lượng.

---

## 3. Danh sách Sample Event hai bên đã đọc và đối chiếu

### 3.1. Nhóm mẫu hợp lệ (`samples/valid/` — Kỳ vọng: Schema PASS)
1. `samples/valid/alert-created-valid.json`: Mẫu chuẩn do nhóm Core Business cung cấp (`alert_id: "ALT-001"`, `severity: "high"`, `target_channels: ["telegram", "email", "sms"]`, `timestamp: "2026-08-27T15:30:00Z"`).
2. `samples/valid/alert-created-boundary.json`: Mẫu biên `alert.created` (`severity: "critical"`, lược bỏ `target_channels` để kiểm tra cơ chế tự định tuyến kênh của Notification).
3. `samples/valid/alert-escalated-valid.json`: Mẫu chuẩn `alert.escalated` (`escalation_level: 2`).
4. `samples/valid/alert-escalated-boundary.json`: Mẫu biên `alert.escalated` ở mức leo thang tối đa (`escalation_level: 5`, đủ 4 kênh đích).
5. `samples/valid/alert-resolved-valid.json`: Mẫu chuẩn `alert.resolved` kèm `resolution_note`.
6. `samples/valid/alert-resolved-boundary.json`: Mẫu biên `alert.resolved` với ghi chú ngắn gọn tối thiểu và kênh chỉ định `["telegram"]`.

### 3.2. Nhóm mẫu không hợp lệ (`samples/invalid/` — Kỳ vọng: Schema FAIL)
1. `samples/invalid/missing-eventId.json`: Thiếu trường bắt buộc `event_id` (`Q02`).
2. `samples/invalid/missing-escalation-level.json`: Event `alert.escalated` thiếu `escalation_level` (`Q02`).
3. `samples/invalid/missing-resolution-note.json`: Event `alert.resolved` thiếu `resolution_note` (`Q02`).
4. `samples/invalid/invalid-severity.json`: `severity` ngoài tập enum `["low", "medium", "high", "critical"]` (`Q03`).
5. `samples/invalid/invalid-timestamp.json`: `timestamp` sai định dạng ISO 8601 `date-time` (`Q03`).
6. `samples/invalid/invalid-target-channel.json`: `target_channels` chứa kênh `"zalo"` không thuộc tập hỗ trợ (`Q03`).
7. `samples/invalid/invalid-source.json`: `source` khác `"core-business"` (`Q04`).
8. `samples/invalid/invalid-event-name.json`: `event_name` là `"alert.deleted"` không thuộc hợp đồng (`Q04`).

---

## 4. Cơ chế nhận biết Duplicate & Nguyên tắc Idempotency

- **Phân biệt rõ `event_id` và `correlationId`:**
  - `event_id` (UUID) định danh duy nhất cho **một lần phát sự kiện cụ thể**.
  - `correlationId` liên kết chuỗi sự kiện (`alert.created` → `alert.escalated` → `alert.resolved`) thuộc cùng một luồng nghiệp vụ.
- **Quy tắc Idempotency tại Consumer (Notification Service):**
  - Consumer lưu `event_id` vào tập/bảng `processed_events` ngay sau khi xử lý thành công.
  - Khi nhận message trùng `event_id` (do cơ chế gửi lại của MQTT/Queue), Consumer trả trạng thái `DUPLICATE_EVENT_SKIPPED`, ACK message và **không phát lại thông báo** ra Telegram/Email/SMS.

---

## 5. Quy tắc Retry / DLQ & Các vấn đề chuyển sang Lab 05 (Khi có Broker thật)

- **Retry Ownership:** Thuộc về **Notification Service (Consumer)**.
- **Tham số Retry:** Tối đa **3 lần retry**, khoảng nghỉ cố định **5 giây** (`interval = 5s`) khi gặp lỗi kết nối/timeout tới dịch vụ gửi tin bên ngoài (Telegram/SMTP/SMS).
- **Dead-Letter Queue (DLQ):** Topic `campus.alerts.dlq`. Message bị đẩy vào DLQ trong 2 trường hợp:
  1. Payload vi phạm JSON Schema (`SCHEMA_VALIDATION_FAILED`) → chuyển thẳng vào DLQ, không retry.
  2. Quá 3 lần retry vẫn gửi thất bại (`MAX_RETRIES_EXCEEDED`) → chuyển vào DLQ kèm `retry_count: 3`.
- **Các nội dung chưa kiểm tra ở Lab 03 (sẽ kiểm tra ở Lab 05 / Plug-a-thon với Broker thật):**
  - Kết nối thực tế và độ ổn định phiên MQTT trên `mqtt://192.168.1.51:1883` trong mạng LAN lớp học.
  - Khả năng chịu tải và độ trễ thực tế khi Core Business bắn burst event liên tiếp lên `campus.alerts`.
  - Kiểm chứng end-to-end việc publish message lỗi sang topic `campus.alerts.dlq` trên broker thật.

---

## 6. Kết luận nghiệm thu

- **Trạng thái:** **READY** cho giai đoạn Implementation (Lab 04) và Broker Integration (Lab 05 / Plug-a-thon).
- **Xác nhận hai bên:**
  - **Đại diện Event Producer (Nhóm 5 — Core Business):** Đã đồng bộ payload `snake_case` và topic `campus.alerts`.
  - **Đại diện Event Consumer (Nhóm 6 — Notification Service):** `<Họ tên / MSSV>` — Đã hoàn tất JSON Schema, bộ mẫu kiểm thử và script tự động PASS 100%.

