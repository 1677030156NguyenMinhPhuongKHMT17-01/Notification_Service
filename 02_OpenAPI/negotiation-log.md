# Biên bản đàm phán hợp đồng API & Event Contract

- **Cặp đàm phán:** Pair #4 — Core Business → Notification Service
- **Product:** Smart Campus Operations Platform (Nhóm 6 — Notification Service)
- **Producer / Upstream:** Nhóm Core Business Service
- **Consumer / Downstream:** Nhóm 6 — Notification Service
- **Phiên:** v1.0 (Đồng bộ `event-contract-04-core-notification.md` & `openapi.yaml`)
- **Ngày:** 2026-08-27

---

## Issue #1 — Cơ chế giao tiếp chính, Địa chỉ Broker và Tên Topic/Event

- **Raised by:** Consumer (Nhóm 6 — Notification Service) & Producer (Nhóm Core Business)
- **Endpoint / Topic:** MQTT Topic `campus.alerts` (`mqtt://192.168.1.51:1883`)
- **Concern:** Trong tài liệu đề bài tổng quát gợi ý gọi HTTP REST hoặc Message Queue, còn trong `pairing-matrix.md` quy định Cặp #4 (`Core Business → Notification`) là bất đồng bộ (`Queue async`). Hai nhóm cần chốt hạ tầng Broker thực tế dùng trên lớp và danh sách tên sự kiện.
- **Proposal:** Sử dụng **MQTT Broker chung của lớp tại `mqtt://192.168.1.51:1883` (Anonymous)** với topic thống nhất là `campus.alerts` cho luồng bất đồng bộ chính, phát 3 sự kiện: `alert.created`, `alert.escalated`, `alert.resolved`. Đồng thời Notification Service mở thêm REST endpoint `POST /notifications` và `GET /notifications` để làm kênh fallback/test và tra cứu log.
- **Resolution:** Accepted
- **Rationale:** Đảm bảo đúng kiến trúc bất đồng bộ của Cặp #4 trong `pairing-matrix.md`, giúp Core Business không bị block khi gửi thông báo đa kênh, đồng thời vẫn có REST API chuẩn OpenAPI 3.1 để kiểm thử bằng Prism/Postman.
- **Impact:** Core Business publish lên `mqtt://192.168.1.51:1883` (topic `campus.alerts`); Notification Service subscribe `campus.alerts` và cung cấp `openapi.yaml` cho REST fallback.

---

## Issue #2 — Quy ước đặt tên trường (`snake_case` vs `camelCase`) và cấu trúc JSON

- **Raised by:** Consumer (Nhóm 6 — Notification Service)
- **Endpoint / Topic:** Topic `campus.alerts` & `POST /notifications`
- **Concern:** Nội bộ Core Business dùng `camelCase` trong OpenAPI của Core, trong khi Notification Service (Python/FastAPI) sử dụng convention `snake_case`. Ngoài ra cần quyết định dùng JSON lồng (`data: {...}`) hay JSON phẳng.
- **Proposal:** Thống nhất dùng **cấu trúc JSON phẳng theo convention `snake_case`** (`event_id`, `event_name`, `source`, `alert_id`, `severity`, `message`, `target_channels`, `escalation_level`, `resolution_note`, `timestamp`), chỉ giữ nguyên tên trường **`correlationId`** để đồng bộ với bộ trace chung của Core Business.
- **Resolution:** Accepted
- **Rationale:** JSON phẳng giúp payload gọn nhẹ trên MQTT, dễ đọc log và parse trực tiếp vào Pydantic model của Notification Service mà không cần bóc tách nhiều tầng.
- **Impact:** Cả 3 sự kiện `alert.created`, `alert.escalated`, `alert.resolved` trong `event-contract-04-core-notification.md` và `openapi.yaml` đều áp dụng cấu trúc `snake_case` phẳng này.

---

## Issue #3 — Giá trị Enum của `severity` và Cơ chế định tuyến kênh (`target_channels`)

- **Raised by:** Producer (Nhóm Core Business)
- **Endpoint / Topic:** Event `alert.created` trên `campus.alerts` & `POST /notifications`
- **Concern:** Event `alert.created` cần những mức `severity` nào và Core Business có bắt buộc phải truyền danh sách kênh gửi trong mọi lần phát cảnh báo hay không?
- **Proposal:**
  1. `severity` là trường **bắt buộc** trong `alert.created`, nhận 1 trong 4 giá trị chữ thường: `low`, `medium`, `high`, `critical`.
  2. Trường `target_channels` là **tùy chọn** (mảng các kênh thuộc `["telegram", "email", "discord", "sms"]`). Nếu Core Business truyền `target_channels`, Notification gửi đúng các kênh đó; nếu không truyền, Notification tự động định tuyến kênh dựa trên `severity`.
- **Resolution:** Accepted
- **Rationale:** Linh hoạt cho cả hai bên: Core Business có thể chỉ định kênh khẩn cấp khi cần (`["telegram", "email", "sms"]`) nhưng không bị phụ thuộc cứng vào logic cấu hình kênh của Notification.
- **Impact:** Notification Service cài đặt bộ Auto-router theo `severity` khi `target_channels` vắng mặt.

---

## Issue #4 — Chống gửi trùng (Idempotency) theo `event_id`

- **Raised by:** Consumer (Nhóm 6 — Notification Service)
- **Endpoint / Topic:** Topic `campus.alerts` & `POST /notifications`
- **Concern:** MQTT/Queue hoạt động theo cơ chế *at-least-once delivery* nên cùng một sự kiện có thể được gửi lặp lại khi mạng chập chờn. Nếu không lọc trùng, người nhận sẽ bị spam nhiều tin nhắn cảnh báo giống hệt nhau.
- **Proposal:** Bắt buộc mọi sự kiện phải có trường `event_id` kiểu UUID duy nhất. Notification Service dùng `event_id` làm **Idempotency Key**: lưu `event_id` đã xử lý vào DB; nếu nhận lại `event_id` trùng trên Queue thì bỏ qua (`duplicate_ignored`), còn nếu gọi qua REST `POST /notifications` thì trả về `409 Conflict`.
- **Resolution:** Accepted
- **Rationale:** Đảm bảo tính idempotent đầu-cuối cho cả luồng Queue async và luồng REST sync fallback.
- **Impact:** Core Business sinh UUID v4 mới cho `event_id` ở mỗi lần publish sự kiện; Notification Service kiểm tra unique constraint trên `event_id`.

---

## Issue #5 — Chính sách Retry và Dead-Letter Queue (DLQ) khi kênh gửi lỗi

- **Raised by:** Consumer (Nhóm 6 — Notification Service)
- **Endpoint / Topic:** Luồng gửi ra Telegram / Email / SMS
- **Concern:** Khi Telegram Bot API hoặc SMTP Email bị lỗi tạm thời (timeout, rate limit), nếu retry phía Producer sẽ làm phức tạp Core Business, còn nếu không retry thì mất cảnh báo quan trọng.
- **Proposal:** `Notification Service` chịu trách nhiệm thực hiện **retry tối đa 3 lần, mỗi lần cách nhau 5 giây (interval 5s)**. Nếu sau 3 lần vẫn thất bại, Notification ghi nhận `status: "failed"`, lưu lý do vào `error_detail` và đẩy sự kiện vào **Dead-Letter Queue (`campus.alerts.dlq`)** để xử lý hậu kiểm.
- **Resolution:** Accepted
- **Rationale:** Tách biệt hoàn toàn lỗi hạ tầng gửi tin nhắn khỏi Core Business, đồng thời có thông số retry cụ thể (`3 lần, interval 5s`) để kiểm thử ở Lab 03.
- **Impact:** Thêm trường `retry_count` (khi auto-retry chạy tối đa 3 lần; cho phép `>= 0` ở schema `NotificationLog` để hỗ trợ kích hoạt gửi lại thủ công `POST /notifications/{notification_id}/retry` ở các Lab triển khai sau) và `error_detail` vào schema `NotificationLog`.

---

## Issue #6 — Chuẩn hóa Error Model (RFC 9457 Problem Details) và Union Type `null` trong OpenAPI 3.1

- **Raised by:** Consumer & Provider
- **Endpoint / Topic:** Toàn bộ REST API `/health`, `/notifications`, `/notifications/recent`, `/notifications/{notification_id}`
- **Concern:** Cần thống nhất định dạng trả về khi gọi REST API bị lỗi (`400`, `401`, `404`, `409`, `422`, `500`, `503` cho `/health`) và cách biểu diễn các trường có thể nhận giá trị `null` (như `error_detail`, `delivered_at`, `next_cursor`, `severity`) theo đúng chuẩn OpenAPI 3.1.0 (không dùng `nullable: true` của 3.0).
- **Proposal:**
  1. Tất cả response lỗi 4xx/5xx đều dùng `application/problem+json` với schema `Problem` theo chuẩn **RFC 9457 Problem Details** (`type`, `title`, `status`, `detail`, `instance`, `errors`). Bỏ mã `403` chưa dùng khỏi `GET /notifications/recent` và bổ sung `503 ServiceUnavailable` cho `GET /health`.
  2. Các trường có thể rỗng như `error_detail`, `delivered_at`, `next_cursor`, hoặc `NotificationLog.severity` (khi một số bản ghi sự kiện không gắn mức độ) khai báo theo chuẩn JSON Schema 2020-12 / OpenAPI 3.1 (`type: [string, "null"]` hoặc `oneOf` với `type: "null"`).
- **Resolution:** Accepted
- **Rationale:** Tuân thủ nghiêm ngặt đặc tả OpenAPI 3.1.0 và vượt qua bộ quy tắc kiểm tra tự động `campus-spectral.yaml` (`campus-no-nullable` cấm dùng `nullable: true`).
- **Impact:** Áp dụng thống nhất trong `openapi.yaml` của cả hai nhóm.

---

## Issue #7 — Đối soát & Chuẩn hóa Schema Canonical Pair 04 (v1.0 Reconciled)

- **Raised by:** Consumer (Nhóm 6 — Notification Service) & QA Contract Review
- **Endpoint / Topic:** Topic `campus.alerts` (`alert.created`, `alert.escalated`, `alert.resolved`), REST `/notifications*`, `/health`, và quy tắc `SEVERITY_ROUTING`
- **Concern:** Khi đối chiếu hợp đồng Lab 02 (`02_OpenAPI/openapi.yaml`, `docs/analysis-provider.md`) với bộ kiểm thử hợp đồng chuẩn Pair 04 ở Lab 03 (`03_Postman/queue-contract-tests/pair-04-core-notification/event-contract.md` và JSON Schema Draft 2020-12) cùng dịch vụ thực thi (Lab 04–05), phát hiện các điểm lệch cần chốt thống nhất:
  1. Pattern `alert_id` cũ `^ALT-[0-9]{3,6}$` chặn các ID dài hơn 6 chữ số trong khi canonical schema dùng `^ALT-[0-9]{3,}$`.
  2. `correlationId` có thể là chuỗi ngắn (tối thiểu 1 ký tự `minLength: 1`) thay vì `minLength: 4`.
  3. `AlertEscalatedEvent.escalation_level` chuẩn là `1..5` (thay vì `1..10`), và cần cho phép thêm trường tùy chọn `severity` (`SeverityLevel`) và `message` (5–500 ký tự).
  4. `AlertResolvedEvent` có thể đính kèm trường tùy chọn `target_channels`.
  5. Bảng định tuyến `SEVERITY_ROUTING` trong `docs/analysis-provider.md` trước đây thiếu kênh `email` ở mức `medium` và thiếu kênh `discord` ở mức `high` / `critical` so với schema `NotificationChannel` (`telegram`, `email`, `discord`, `sms`).
  6. Các mở rộng vận hành v1.x ở Lab 04–05 như `POST /notifications/{notification_id}/retry` (cho phép `retry_count >= 0`) và `GET /ready` (kiểm tra Postgres + MQTT ở Lab 05) cần được ghi nhận ranh giới so với hợp đồng nền v1.0.
- **Proposal:**
  1. Chuẩn hóa `openapi.yaml` theo canonical Pair 04: `alert_id` pattern `^ALT-[0-9]{3,}$`, `correlationId` `minLength: 1`, `escalation_level` `1..5`, bổ sung optional `severity`/`message` cho `AlertEscalatedEvent` và optional `target_channels` cho `AlertResolvedEvent`, `NotificationLog.severity` hỗ trợ `null` qua `oneOf`, bỏ `maximum: 3` trên `NotificationLog.retry_count`, thêm `503` cho `GET /health` và gỡ `403` khỏi `GET /notifications/recent`.
  2. Đồng bộ `docs/analysis-provider.md` và `docs/analysis-consumer.md` với bảng `SEVERITY_ROUTING` đầy đủ (`low`: `[email]`; `medium`: `[telegram, email]`; `high`: `[telegram, email, discord]`; `critical`: `[telegram, email, discord, sms]`).
  3. Giữ `openapi.yaml` của Lab 02 ở hợp đồng nền v1.0 đã ký (`POST /notifications/{notification_id}/retry` và `GET /ready` là phần mở rộng runtime v1.x tại `04_Docker/` và `05_Compose/`, đồng bộ liên thông sang Lab 03).
- **Resolution:** Accepted
- **Rationale:** Đảm bảo 100% tương thích xuôi từ Lab 02 → Lab 03 (`event-contract.md`) → Lab 04/05 mà vẫn giữ Spectral lint `0 errors`.
- **Impact:** Đã cập nhật `02_OpenAPI/openapi.yaml`, `02_OpenAPI/docs/analysis-provider.md`, `02_OpenAPI/docs/analysis-consumer.md` và đối soát với `03_Postman/contracts/notification.openapi.yaml`.

---

# Chốt hợp đồng v1.0

- **Provider / Producer sign-off:** Đại diện Nhóm Core Business — *Đã xác nhận đồng bộ (`event-contract-04-core-notification.md`)*
- **Consumer sign-off:** Đại diện Nhóm 6 (Notification Service) — *Nguyễn Minh Phượng (`<MãSinhViên>`)*
- **Witness (GV/TA):** Giảng viên hướng dẫn học phần FIT4110
- **Date:** 2026-08-27

---

## Ghi chú warning nếu Spectral còn cảnh báo

| Warning | Lý do chấp nhận tạm thời | Kế hoạch sửa |
|---|---|---|
| Không có (`0 errors, 0 warnings`) | File `openapi.yaml` đã pass tuyệt đối toàn bộ ruleset `campus-spectral.yaml` | Duy trì kiểm tra bằng `spectral lint` ở mọi lần cập nhật hợp đồng |
