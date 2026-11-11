# Event Test Matrix — Pair 04: Core Business → Notification Service

> Tài liệu này mô tả ma trận kiểm thử hợp đồng Queue Async cho **Pair 04 (`Core Business → Notification Service`)** theo chuẩn Mục 8 và Mục 9 của `Lab03_Kiểm thử Queue-Async.pdf`.

---

## 1. Bảng Test Matrix bắt buộc (`Q01–Q09`)

| Mã | Tình huống | Mức kiểm thử | Dữ liệu mẫu / Stub Test | Kỳ vọng Lab 03 | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|---|
| **Q01** | Event hợp lệ, đủ field, đúng kiểu dữ liệu cho cả 3 loại event (`alert.created`, `alert.escalated`, `alert.resolved`) và trường hợp biên (tự động định tuyến kênh khi vắng `target_channels`, `escalation_level=5`) | **Mức A** (JSON Schema tự động) | `samples/valid/alert-created-valid.json`<br>`samples/valid/alert-created-boundary.json`<br>`samples/valid/alert-escalated-valid.json`<br>`samples/valid/alert-escalated-boundary.json`<br>`samples/valid/alert-resolved-valid.json`<br>`samples/valid/alert-resolved-boundary.json` | Schema **PASS** (`[PASS]`) | **PASS** (6/6 file valid) | `reports/event-contract-test.txt` |
| **Q02** | Thiếu field bắt buộc: thiếu `event_id` (trong `alert.created`), thiếu `escalation_level` (trong `alert.escalated`), thiếu `resolution_note` (trong `alert.resolved`) | **Mức A** (JSON Schema tự động) | `samples/invalid/missing-eventId.json`<br>`samples/invalid/missing-escalation-level.json`<br>`samples/invalid/missing-resolution-note.json` | Schema **FAIL** (`[PASS expected-invalid]`) | **PASS** (Schema từ chối cả 3 file) | `reports/event-contract-test.txt` |
| **Q03** | Sai enum / type / format: `severity: "EXTREME_URGENT"` ngoài enum, `timestamp: "27/08/2026 15:30:00"` sai ISO 8601, `target_channels: ["telegram", "zalo"]` chứa kênh không hỗ trợ | **Mức A** (JSON Schema tự động) | `samples/invalid/invalid-severity.json`<br>`samples/invalid/invalid-timestamp.json`<br>`samples/invalid/invalid-target-channel.json` | Schema **FAIL** (`[PASS expected-invalid]`) | **PASS** (Schema từ chối cả 3 file) | `reports/event-contract-test.txt` |
| **Q04** | `event_name` hoặc `source` không đúng contract: `source: "unknown-producer"` (khác `"core-business"`), `event_name: "alert.deleted"` (ngoài 3 event đã ký) | **Mức A** (JSON Schema tự động) | `samples/invalid/invalid-source.json`<br>`samples/invalid/invalid-event-name.json` | Schema **FAIL** (`[PASS expected-invalid]`) | **PASS** (Schema từ chối cả 2 file) | `reports/event-contract-test.txt` |
| **Q05** | Cùng `event_id` xuất hiện hai lần (Duplicate delivery do QoS At-Least-Once của MQTT/Queue) | **Mức B** (Semantic + Consumer Stub) | `Q05-duplicate-eventId-idempotency` trong `scripts/test-event-contract.js` | Consumer kiểm tra `event_id` trong bảng `processed_events`; lần 1 gửi thông báo (`SENT`), lần 2 bỏ qua (`DUPLICATE_EVENT_SKIPPED`), không lặp thao tác gửi Telegram/Email/SMS | **PASS** (`[PASS semantic-stub] Q05`) | `reports/event-contract-test.txt` |
| **Q06** | Consumer xử lý lỗi tạm thời từ cổng gửi thông báo (Telegram/SMTP/SMS timeout hoặc `5xx`) | **Mức B** (Semantic + Consumer Stub) | `Q06-consumer-retry-within-limit` trong `scripts/test-event-contract.js` | **Retry Owner:** Notification Service (Consumer). Thực hiện retry tối đa **3 lần**, cách nhau **5 giây** (`interval = 5s`). Nếu thành công ở lần retry thứ 2 (tổng 3 lần thử) → đánh dấu `SENT` | **PASS** (`[PASS semantic-stub] Q06`) | `reports/event-contract-test.txt` |
| **Q07** | Retry hết giới hạn (quá 3 lần retry vẫn lỗi) hoặc message sai schema | **Mức B** (Semantic + Consumer Stub) | `Q07-dlq-after-3-retries` trong `scripts/test-event-contract.js` | Chuyển message lỗi sang Dead-Letter Queue / Topic **`campus.alerts.dlq`** kèm metadata `reason`, `retry_count: 3`, `retry_interval_seconds: 5` để cách ly message lỗi, không làm nghẽn hàng đợi chính | **PASS** (`[PASS semantic-stub] Q07`) | `reports/event-contract-test.txt` |
| **Q08** | Event hoặc version không hỗ trợ (`event_name` lạ hoặc payload có field lạ vi phạm `additionalProperties: false`) | **Mức B** (Semantic + Consumer Stub) | `Q08-unsupported-event-rejected` trong `scripts/test-event-contract.js` | Từ chối ngay tại tầng JSON Schema Validator (không retry vô ích) và chuyển vào `campus.alerts.dlq` với lý do `SCHEMA_VALIDATION_FAILED` | **PASS** (`[PASS semantic-stub] Q08`) | `reports/event-contract-test.txt` |
| **Q09** | Event đến trễ hoặc out-of-order (`alert.resolved` có `timestamp` `17:00Z` đến trước `alert.created` có `timestamp` `16:50Z` của cùng `alert_id`) | **Mức B** (Semantic + Consumer Stub) | `Q09-out-of-order-event-suppressed` trong `scripts/test-event-contract.js` | Consumer đối chiếu `alert_id` và `timestamp`: vì `ALT-060` đã ở trạng thái `RESOLVED` tại thời điểm mới hơn (`17:00Z`), sự kiện `alert.created` đến trễ (`16:50Z`) được ghi nhận audit nhưng gắn cờ `SUPPRESSED_OUT_OF_ORDER`, không báo động giả | **PASS** (`[PASS semantic-stub] Q09`) | `reports/event-contract-test.txt` |

---

## 2. Điểm kiểm thử đặc thù của Pair 04 (`Core Business → Notification`)

Theo Mục 9 của `Lab03_Kiểm thử Queue-Async.pdf`, các điểm đặc thù của Pair 04 đã được kiểm chứng cụ thể như sau:

1. **`severity` & Quy tắc tự định tuyến kênh (`target_channels`):**
   - Kiểm tra enum nghiêm ngặt: `["low", "medium", "high", "critical"]`.
   - Khi `target_channels` có mặt (`alert-created-valid.json`: `["telegram", "email", "sms"]`), Consumer gửi đúng danh sách kênh được chỉ định.
   - Khi `target_channels` vắng mặt (`alert-created-boundary.json`: `severity = "critical"`), Consumer tự động ánh xạ sang `["telegram", "email", "discord", "sms"]`.
2. **Dedupe theo `event_id` (không nhầm với `correlationId`):**
   - `event_id` là UUID định danh duy nhất cho **từng message event** (khác nhau giữa `alert.created`, `alert.escalated`, `alert.resolved`).
   - `correlationId` (`req-0196fb3d-4ad7-7d1e-9f49-5d5148d2babc`) giữ nguyên xuyên suốt vòng đời của cùng một sự cố `ALT-001` để phục vụ distributed tracing.
   - Dedupe chỉ khóa trên `event_id` để đảm bảo `alert.escalated` và `alert.resolved` có cùng `correlationId` và `alert_id` vẫn được xử lý bình thường.
3. **Retry Ownership & Dead-Letter Queue (`DLQ`):**
   - **Owner:** Notification Service (Consumer) chịu trách nhiệm retry khi kênh gửi bên ngoài (Telegram/Email/SMS) lỗi.
   - **Tham số:** Tối đa 3 lần retry, mỗi lần cách nhau 5 giây.
   - **DLQ:** Topic `campus.alerts.dlq`.

