# Fault Injection & Recovery Runbook — Notification Service (Nhóm 6 / A7 / B7)

Sổ tay thao tác tiêm lỗi (fault injection) có kiểm soát, kiểm chứng khả năng chịu lỗi và quy trình phục hồi dịch vụ cho **Lab 06 Plug-a-thon**.

---

## 1. Bảng ma trận các kịch bản tiêm lỗi chuẩn

| Mã | Kịch bản lỗi | Cơ chế kích hoạt | Kết quả kỳ vọng (Contract & Runtime) | Cách phục hồi (Recovery) |
| :--- | :--- | :--- | :--- | :--- |
| **F1 (`Q08`)** | **Invalid JSON / Schema Violation trên MQTT** | Gửi event `event_name: "alert.deleted"`, `severity: "EXTREME"` qua `scripts/core_business_simulator.py --scenario invalid-schema` (hoặc `run_plugathon_e2e.py`) | Pydantic v2 `event_adapter` (`extra="forbid"`) bắt lỗi ngay; **không retry** (`retry_count: 0`); đẩy envelope sang **`campus.alerts.dlq`** với `reason="SCHEMA_VALIDATION_FAILED"` kèm `source_topic`, `original_payload`, `error_detail`, `failed_at`. API vẫn khỏe (`200`), không crash worker. | Producer sửa payload đúng [campus.alerts.schema.json](../contracts/schema/campus.alerts.schema.json) và gửi event mới với `event_id` mới. |
| **F2 (`Q07`)** | **Kênh downstream sập & vượt quá giới hạn retry** | Đặt `FAIL_CHANNELS=sms`, `MAX_RETRIES=0` (hoặc giữ `MAX_RETRIES=3` đợi `~15s`), recreate `api`: `docker compose up -d --no-deps --wait api`, rồi gửi `alert.created` tới `sms`. | `delivery.py` fail ở kênh `sms`; sau khi hết retry, Postgres ghi `status="failed"`, `sent=false`, và `MqttConsumer` đẩy envelope sang **`campus.alerts.dlq`** với `reason="MAX_RETRIES_EXCEEDED"` kèm `notification_id`, `event_id`, `alert_id`, `retry_count`. | Xóa fault env (`FAIL_CHANNELS=""`, `MAX_RETRIES=3`), recreate `api`, rồi gọi **`POST /notifications/{notification_id}/retry`** → `status="delivered"`, `sent=true`, `retry_count` tăng lên. |
| **F3 (`Q09`)** | **Event đến sai thứ tự (`Out-of-Order`)** | Publish `alert.resolved` (`T=now`), tiếp theo publish `alert.created` trễ hơn (`T=now-10m`) cho cùng `alert_id` (`scripts/core_business_simulator.py --scenario ooo`). | So sánh cột `event_timestamp` trong Postgres phát hiện sự cố đã đóng sau mốc thời gian của event mới tới → chặn gửi ra kênh ngoài; lưu `status="duplicate_ignored"`, `sent=false`, `error_detail="SUPPRESSED_OUT_OF_ORDER:..."`. | Không cần retry; thông báo giả/cũ đã bị triệt tiêu an toàn theo đúng test case `Q09`. |
| **F4 (`Q05`)** | **Duplicate `event_id` (MQTT Replay & REST Double-Submit)** | Publish trùng `event_id` lên MQTT hoặc gửi `POST /notifications` 2 lần cùng `event_id`. | Ràng buộc `event_id UNIQUE` trong PostgreSQL bảo vệ idempotency bền vững kể cả sau restart container: MQTT skip không gửi đúp; REST trả HTTP **`409 Conflict`** chuẩn RFC 9457. | Tự động chống trùng, không phát sinh thông báo thừa. |
| **F5** | **Khởi động lại container giữa lúc `retrying` / Broker gián đoạn** | Tạm dừng broker (`docker compose stop mqtt-broker`), kiểm tra `/ready`; hoặc recreate `api` khi bản ghi đang `retrying`. | Khi broker tắt, `GET /health` vẫn `200` (DB sống) còn `GET /ready` chuyển HTTP **`503`** (`mqtt.connected: false`). Khi `api` khởi động lại, `store.init()` chuyển các bản ghi kẹt ở `retrying` về `failed` để operator nhìn thấy. | Khởi động lại broker (`docker compose start mqtt-broker`), chờ `/ready` về `200`, gọi `POST /notifications/{id}/retry` cho các bản ghi `failed`. |
| **F6** | **Sai xác thực / Payload REST bất hợp lệ** | Gửi request thiếu/sai Bearer token; hoặc body `target_channels: ["zalo"]`; hoặc `GET /notifications/recent?limit=101`. | Trả chuẩn **RFC 9457 (`application/problem+json`)**: `401 Unauthorized` (thiếu/sai token), `422 Unprocessable Entity` (kênh `zalo`), `400 Bad Request` (`limit=101`), `404 Not Found` (`notification_id` không tồn tại). | Client sửa header/payload đúng [endpoint_catalog.md](endpoint_catalog.md). |

---

## 2. Quy trình thực hành bằng 1 lệnh (Tự động hóa)

Để chạy toàn bộ chuỗi kiểm tra F1, F2 (bao gồm tạm tiêm `FAIL_CHANNELS=sms MAX_RETRIES=0`, xác nhận `campus.alerts.dlq` nhận `MAX_RETRIES_EXCEEDED`, gỡ biến lỗi và phục hồi qua `POST /notifications/{id}/retry`), F3, F4, F6:

```bash
cd FIT4110_MSSV/06_Plugathon
python scripts/run_plugathon_e2e.py --with-compose-dlq-recovery
```

Hoặc qua Make:

```bash
make e2e
```

---

## 3. Thao tác kiểm chứng thủ công DLQ & Recovery (khi live demo / quay video)

1. Mở terminal 1 xem log realtime của Notification Service:
   ```bash
   docker compose logs -f api
   ```
2. Tiêm lỗi kênh `sms` không auto-retry:
   ```bash
   FAIL_CHANNELS=sms MAX_RETRIES=0 docker compose up -d --no-deps --wait api
   ```
3. Gửi event `critical` (có kênh `sms`) bằng `POST /notifications` hoặc publish MQTT → quan sát bản ghi trong `GET /notifications/recent` mang `status: "failed"` và thông điệp `MAX_RETRIES_EXCEEDED` trên `campus.alerts.dlq`.
4. Khôi phục cấu hình sạch và gọi Manual Retry:
   ```bash
   FAIL_CHANNELS= MAX_RETRIES=3 docker compose up -d --no-deps --wait api
   # Đợi GET /ready trả HTTP 200 trước khi retry
   curl -fsS -X POST "http://localhost:8000/notifications/<NOTIFICATION_ID>/retry" \
     -H "Authorization: Bearer plugathon-dev-token"
   ```
   Kết quả trả về HTTP `200` với `"status": "delivered"`, `"sent": true` và `"retry_count": 1`.
5. Ghi nhận đầy đủ mã sự cố, timestamp, log và kết quả vào [evidence/fault_record.md](../evidence/fault_record.md) (file do verification owner cập nhật khi chạy thực tế).

