# Integration Notes — Pair 04 & Plug-a-thon Onboarding (`Core Business -> Notification Service`)

Hướng dẫn kỹ thuật ngắn gọn để nhóm đối tác (**Core Business — Nhóm 5 / A6 / B6**, **Analytics / Dashboard**, và ban kiểm tra Plug-a-thon) kết nối chính xác với **Notification Service (`Nhóm 6 / A7 / B7`)**.

---

## 1. Kết nối tới Notification Service trên mạng lớp (`class-net`) & LAN

| Chế độ triển khai | Địa chỉ Broker MQTT (`campus.alerts`) | Base URL REST API của Notification | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Standalone cục bộ** | `mqtt://127.0.0.1:1883` (host) / `mqtt://mqtt-broker:1883` (Docker) | `http://localhost:8000` | Dùng cho kiểm thử cô lập trên 1 máy. |
| **Plug-a-thon `class-net`** | `${MQTT_BROKER_URL}` (mặc định overlay: `mqtt://192.168.1.51:1883`) | `http://notification-service:8000` (alias trên `class-net`) hoặc `http://<HOST_IP>:${APP_PORT:-8000}` | Khởi chạy bằng `docker compose -f docker-compose.yml -f docker-compose.external-broker.yml up -d --build --wait`. |

- **Điều kiện mạng:** Cần tạo trước Docker bridge chung nếu cùng host: `docker network create class-net`.
- **Không hard-code IP:** Thay đổi IP broker bất kỳ lúc nào qua biến `MQTT_BROKER_URL` khi khởi chạy Compose mà không cần build lại container.

---

## 2. Hợp đồng giao tiếp Pair 04 (Producer Checklist cho Core Business)

1. **Topic & QoS:** Publish lên **`campus.alerts`** với **QoS 1** (`retain=False`). Không publish trực tiếp sang `campus.alerts.dlq` (topic DLQ chỉ do Notification ghi khi reject/fail).
2. **Cấu trúc JSON phẳng (`snake_case` + `correlationId`):**
   - Dùng trực tiếp các trường gốc (`event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `timestamp`, ...); **không bọc** vào envelope `{payload: {...}}` hay đặt `correlation_id`.
   - `event_id`: UUID v4 duy nhất cho mỗi sự kiện. Nếu retry mạng dẫn tới gửi trùng `event_id`, Notification sẽ khử trùng lặp idempotent (`Q05`).
   - `alert_id`: Bắt buộc khớp regex `^ALT-[0-9]{3,}$` (ví dụ `ALT-601`, `ALT-1001`).
   - `source`: `"core-business"`.
   - `timestamp`: Chuỗi ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`).
3. **3 loại sự kiện hợp lệ & Hành vi kênh:**
   - **`alert.created`:** Yêu cầu `severity` (`low` | `medium` | `high` | `critical`) và `message`. Có thể bỏ qua `target_channels` để Notification tự chọn theo `SEVERITY_ROUTING` (`low→[email]`, `medium→[telegram,email]`, `high→[telegram,email,discord]`, `critical→[telegram,email,discord,sms]`).
   - **`alert.escalated`:** Yêu cầu `escalation_level` (`1..5`); cho phép truyền thêm các trường optional `severity`, `message`, `target_channels` để đồng bộ nội dung leo thang.
   - **`alert.resolved`:** Yêu cầu `resolution_note` (`3..500` ký tự); cho phép truyền thêm `target_channels`. Notification ghi nhận mốc thời gian đóng để chặn mọi `alert.created`/`alert.escalated` cũ đến muộn (`Q09 SUPPRESSED_OUT_OF_ORDER`).
4. **Cảnh báo `extra="forbid"`:** JSON Schema Draft 2020-12 đặt `additionalProperties: false` — mọi field thừa không nằm trong hợp đồng đều bị đẩy vào `campus.alerts.dlq` với `SCHEMA_VALIDATION_FAILED`.

---

## 3. REST Consumer & Sync Fallback (Analytics / Operator / Core Business)

- **Header bắt buộc cho `/notifications*`:** `Authorization: Bearer <AUTH_TOKEN>` (giá trị mặc định dev trong `.env.example`: `plugathon-dev-token`).
- **Health & Readiness probes (không yêu cầu token):**
  - `GET /health` → `200` khi tiến trình FastAPI sống và ping PostgreSQL thành công (`SELECT 1`), ngược lại `503`.
  - `GET /ready` → `200` khi cả PostgreSQL (`dependencies.database.ready=true`) và kết nối tới MQTT broker lớp (`dependencies.mqtt.connected=true`) đều sẵn sàng; ngược lại `503`.
- **Pagination:** `GET /notifications` nhận `limit` (`1..100`), `cursor`, `alert_id`, `status`, `channel`. `GET /notifications/recent` nhận `limit` (`1..100`; giá trị `>100` như `101` trả `400 application/problem+json`).
- **Recovery:** Khi một sự kiện bị `status: "failed"`, operator tra cứu `notification_id` và gọi `POST /notifications/{notification_id}/retry`.

---

## 4. Điểm lưu ý về Hợp đồng đối tác (`core-business.openapi.yaml`)

- File [contracts/core-business.openapi.yaml](../contracts/core-business.openapi.yaml) (`v1.0.0`) được giữ nguyên **read-only** theo đúng **Luật 1 & Luật 2** (chỉ Nhóm 5 được sửa).
- Lưu ý đối tác chưa đổi tên ví dụ `service: lab02-contract-template` tại `/health` trong `core-business.openapi.yaml` và dùng `camelCase` cho REST entity `Alert` trong nội bộ Core Business; điều này **không** ảnh hưởng tới Pair 04 vì bus MQTT Pair 04 đã thống nhất phẳng theo [event-contract.md](../contracts/event-contract.md) (chi tiết xem [known-issues.md](../known-issues.md)).

