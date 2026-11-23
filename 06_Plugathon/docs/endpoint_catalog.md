# Endpoint & Async Event Catalog — Notification Service (Nhóm 6 / A7 / B7)

Danh mục chính thức các REST endpoints và kênh MQTT thuộc **Notification Service** dựa trên hợp đồng đã đóng băng ở Lab 06 ([notification.openapi.yaml](../contracts/notification.openapi.yaml) `v1.0.0`, OpenAPI 3.1.0 & Pair-04 schemas trong [contracts/schema/](../contracts/schema/campus.alerts.schema.json)).

---

## 1. Cấu hình nền tảng REST API

| Thành phần | Giá trị chuẩn hóa |
| :--- | :--- |
| **Base URL (Docker standalone)** | `http://localhost:${APP_PORT:-8000}` |
| **Base URL (`class-net` Plug-a-thon)** | `http://notification-service:8000` (qua Docker network alias trong [docker-compose.external-broker.yml](../docker-compose.external-broker.yml)) |
| **Swagger UI / OpenAPI JSON** | `/docs`, `/redoc`, `/openapi.json` |
| **Xác thực (`BearerAuth`)** | `Authorization: Bearer <AUTH_TOKEN>` (bắt buộc cho toàn bộ nhóm `/notifications*`; mặc định dev `.env.example`: `plugathon-dev-token`) |
| **Chuẩn phản hồi lỗi** | **RFC 9457 Problem Details** (`Content-Type: application/problem+json` gồm `type`, `title`, `status`, `detail`, `instance`, tùy chọn `errors`) |

---

## 2. Bảng tổng hợp REST Endpoints (7 Endpoints)

| Method | Path | Auth | Success Status | Error Status (`application/problem+json`) | Mục đích & Hành vi chính |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | Không | `200 OK` | `503 Service Unavailable` | Liveness & DB ping (`SELECT 1` trên PostgreSQL); trả `status`, `service`, `version`, `env`, `mqtt_enabled`, `subscribed_topic`, `dlq_topic`. |
| `GET` | `/ready` | Không | `200 OK` | `503 Service Unavailable` | Readiness gate: chỉ trả `200` khi cả `dependencies.database.ready == true` và `dependencies.mqtt.connected == true` (khi `MQTT_ENABLED=true`). |
| `POST` | `/notifications` | Bearer | `201 Created` | `400`, `401`, `409`, `422` | Tiếp nhận đồng bộ 1 trong 3 event Pair 04 (`alert.created`, `alert.escalated`, `alert.resolved`), định tuyến kênh và lưu `NotificationLog`. Trùng `event_id` trả `409`. |
| `GET` | `/notifications` | Bearer | `200 OK` | `400`, `401`, `422` | Tra cứu danh sách log gửi kèm lọc (`alert_id`, `status`, `channel`) và phân trang **cursor** (`limit` `1..100`, mặc định `20`, trả `next_cursor`). |
| `GET` | `/notifications/recent` | Bearer | `200 OK` | `400`, `401`, `422` | Trả danh sách thông báo mới nhất theo thứ tự giảm dần (`limit` `1..100`, mặc định `20`; `limit=101` bị chặn với `400 ProblemDetails`). |
| `GET` | `/notifications/{notification_id}` | Bearer | `200 OK` | `401`, `404` | Tra cứu chi tiết 1 bản ghi `NotificationLog` theo `notification_id` (`notif-...`). Không tồn tại trả `404`. |
| `POST` | `/notifications/{notification_id}/retry` | Bearer | `200 OK` | `401`, `404` | Thực hiện **manual retry** cho bản ghi thông báo; tăng `retry_count`, gọi lại dispatcher và cập nhật trạng thái (`delivered` nếu kênh phục hồi). |

---

## 3. Chi tiết Request / Response & Quy tắc Validation

### 3.1. `POST /notifications` (Sync Fallback / REST Test Ingress)
Chấp nhận discriminated union theo `event_name` (Pydantic `extra="forbid"`, mọi trường thừa đều bị từ chối với `422`):

| `event_name` | Trường bắt buộc (`required`) | Trường tùy chọn (`optional`) | Quy tắc đặc biệt |
| :--- | :--- | :--- | :--- |
| `alert.created` | `event_id` (UUID), `event_name`, `correlationId` (`minLength: 1`), `source` (`"core-business"`), `alert_id` (`^ALT-[0-9]{3,}$`), `severity`, `message` (`minLength: 1`), `timestamp` (ISO 8601 UTC) | `target_channels` (mảng kênh trong `{telegram, email, discord, sms}`) | Nếu bỏ qua `target_channels`, áp dụng `SEVERITY_ROUTING[severity]`. |
| `alert.escalated` | `event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `escalation_level` (int `1..5`), `timestamp` | `severity`, `message`, `target_channels` | Nếu bỏ qua `severity`, fallback `high` khi cần định tuyến mặc định; nếu `severity` được gửi, lưu đúng giá trị vào `NotificationLog`. |
| `alert.resolved` | `event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `resolution_note` (`3..500` ký tự), `timestamp` | `target_channels` | Nếu bỏ qua `target_channels`, dùng kênh `email` hoặc kênh chỉ định; lưu `severity: null` trên `NotificationLog`. |

**Trích xuất cấu trúc `NotificationLog` (`201` / `200`):**
```json
{
  "notification_id": "notif-8a1f2c3d4e5f",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_name": "alert.created",
  "correlationId": "req-cb-601",
  "alert_id": "ALT-601",
  "severity": "high",
  "message": "Cảnh báo mức high tại ALT-601",
  "target_channels": ["telegram", "email", "discord"],
  "sent": true,
  "status": "delivered",
  "retry_count": 0,
  "error_detail": null,
  "created_at": "2026-11-13T10:00:01Z",
  "updated_at": "2026-11-13T10:00:01Z"
}
```

### 3.2. Trạng thái `DeliveryStatus` & Ma trận lỗi REST

- **5 giá trị `DeliveryStatus`:** `queued`, `delivered`, `retrying`, `failed`, `duplicate_ignored`.
- **Ma trận mã lỗi:**
  - `401 Unauthorized`: Thiếu header `Authorization` hoặc sai `<AUTH_TOKEN>`.
  - `400 Bad Request`: JSON hỏng cú pháp, hoặc vi phạm ràng buộc query (`limit=0`, `limit=101`), hoặc `cursor` không hợp lệ.
  - `404 Not Found`: Không tìm thấy `notification_id` trong PostgreSQL/Memory store.
  - `409 Conflict`: `event_id` đã tồn tại (REST idempotency check).
  - `422 Unprocessable Entity`: Sai định dạng Pydantic/JSON Schema trong request body (ví dụ `target_channels: ["zalo"]`, `alert_id: "BAD-1"`, `escalation_level: 9`, hoặc thiếu field bắt buộc).
  - `503 Service Unavailable`: `/health` mất kết nối DB hoặc `/ready` chưa kết nối xong DB/MQTT.

---

## 4. Kênh MQTT Bất đồng bộ (Pair 04 Contract)

| Topic | QoS / Session | Hướng | Cấu trúc & Quy tắc xử lý |
| :--- | :--- | :--- | :--- |
| **`campus.alerts`** | QoS `1`, `clean_session=False` | Core Business → Notification | Flat JSON `snake_case` (trừ `correlationId`), validate bằng [campus.alerts.schema.json](../contracts/schema/campus.alerts.schema.json). Trùng `event_id` → skip idempotent (`Q05`). Event đến trễ hơn `alert.resolved` → `duplicate_ignored` với `SUPPRESSED_OUT_OF_ORDER` (`Q09`). |
| **`campus.alerts.dlq`** | QoS `1` | Notification → Operator / CI | Nhận 2 loại bản ghi chết: **`SCHEMA_VALIDATION_FAILED`** (`retry_count: 0`, kèm `topic`, `source_topic`, `original_payload`, `error_detail`, `failed_at`) và **`MAX_RETRIES_EXCEEDED`** (khi hết `MAX_RETRIES × RETRY_INTERVAL_SECONDS` mà kênh trong `FAIL_CHANNELS` hoặc webhook vẫn lỗi; kèm `notification_id`, `event_id`, `alert_id`, `retry_count`, `notification`). |

### Ma trận định tuyến theo mức độ (`SEVERITY_ROUTING` trong `store.py`)

| Severity | Kênh mặc định khi không truyền `target_channels` |
| :--- | :--- |
| `low` | `["email"]` |
| `medium` | `["telegram", "email"]` |
| `high` | `["telegram", "email", "discord"]` |
| `critical` | `["telegram", "email", "discord", "sms"]` |

