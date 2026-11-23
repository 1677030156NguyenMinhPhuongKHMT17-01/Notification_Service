# Biên bản Tiêm lỗi, Dead-Letter Queue & Phục hồi — Lab 06 Plug-a-thon

Biên bản này ghi nhận **kết quả thực tế đã chạy và thu thập trực tiếp** trên stack Docker Compose Lab 06 (`fit4110-api-lab06`, `fit4110-db-lab06`, `fit4110-mqtt-lab06`) ngày `2026-11-13` (giờ UTC `11:45–11:48Z`, tức `18:45–18:48+07:00`).

> Mọi `notification_id`, `event_id`, `correlationId`, timestamp và payload DLQ dưới đây đều trích nguyên văn từ log thu trực tiếp tại [logs/dlq-fault.log](logs/dlq-fault.log), [logs/plugathon-e2e.log](logs/plugathon-e2e.log) và [logs/api-container.log](logs/api-container.log).

---

## 1. Tóm tắt các kịch bản lỗi & phục hồi đã kiểm chứng

| Mã | Kịch bản tiêm lỗi | Tham số / Trigger thực tế | Kết quả quan sát trên Broker / REST / DB | Trạng thái |
|---|---|---|---|---|
| **F1 (`Q08`)** | Payload sai schema trên MQTT (`alert.deleted`, `severity="EXTREME"`) | `core_business_simulator.py --scenario invalid-schema` + `run_plugathon_e2e.py` | Bắt lỗi ngay bởi Pydantic v2 `event_adapter`, không retry (`retry_count=0`), đẩy sang `campus.alerts.dlq` với `reason="SCHEMA_VALIDATION_FAILED"` | **PASS** |
| **F2 (`Q07`)** | Kênh downstream lỗi & vượt retry (`FAIL_CHANNELS=sms`, `MAX_RETRIES=0`) → Recovery | Recreate `api` với `FAIL_CHANNELS=sms MAX_RETRIES=0`, gửi `alert.created` (`critical`, `target_channels=["sms"]`), sau đó gỡ lỗi & gọi `POST /notifications/{id}/retry` | Bản ghi lưu `status="failed"`, phát DLQ `reason="MAX_RETRIES_EXCEEDED"`; sau khi gỡ `FAIL_CHANNELS=""` và gọi `/retry`, trả HTTP `200` với `status="delivered"`, `sent=true`, `retry_count=1` | **PASS** |
| **F3 (`Q09`)** | Sự kiện đến sai thứ tự (`alert.created` trễ hơn `alert.resolved`) | `core_business_simulator.py --scenario ooo --ooo-alert-id ALT-690` (`T_created = T_resolved - 10m`) | `alert.resolved` giao thành công; `alert.created` trễ bị triệt tiêu với `status="duplicate_ignored"`, `sent=false`, `error_detail="SUPPRESSED_OUT_OF_ORDER: ..."` | **PASS** |
| **F4 (`Q05`)** | Trùng `event_id` trên MQTT & REST | Gửi lặp `event_id` trên `campus.alerts` và gọi lại `POST /notifications` | MQTT giữ đúng `stored_rows=1`; REST trả HTTP `409 Conflict` chuẩn RFC 9457 | **PASS** |
| **F5 (REST)** | Thiếu/sai Bearer token, kênh không hợp lệ (`zalo`), `limit=101` | Gọi `POST /notifications` (token sai / channel `["zalo"]`) & `GET /notifications/recent?limit=101` | Trả đúng RFC 9457 `application/problem+json`: `401 Unauthorized`, `422 Unprocessable Entity`, `400 Bad Request` | **PASS** |
| **F6 (Harness)** | Race condition phát hiện khi chạy lần đầu `demo/run_demo.ps1` | `_poll_recent_by_event_id` đọc trúng trạng thái trung gian `queued` trước khi `_attempt()` ghi xong `failed` | Đã báo `@plugathon-infra` sửa `_poll_recent_by_event_id` chờ terminal status (`delivered`/`failed`/`duplicate_ignored`); chạy lại từ sạch đạt `13/13` PASS | **FIXED & VERIFIED** |

---

## 2. Chi tiết bằng chứng từng kịch bản tiêm lỗi

### 2.1. Fault 1 (`Q08`) — `SCHEMA_VALIDATION_FAILED` trên `campus.alerts.dlq`

- **Phiên thu log chuyên sâu (`logs/dlq-fault.log`):**
  - `alert_id`: `ALT-601`
  - `event_id`: `8974d986-ef6d-4e3a-a5b7-6482a8e24b53`
  - `correlationId`: `req-fault-schema-0b80c0`
  - `observed_at` trên broker: `2026-11-13T11:47:22Z`
  - **Thông điệp DLQ thu trực tiếp trên topic `campus.alerts.dlq`:**
    - `reason`: `SCHEMA_VALIDATION_FAILED`
    - `retry_count`: `0`
    - `failed_at`: `2026-11-13T11:47:22Z`
    - `source_topic`: `campus.alerts`
    - `error_detail`: `1 validation error for tagged-union[AlertCreatedEvent,AlertEscalatedEvent,AlertResolvedEvent] ... Input tag 'alert.deleted' found using 'event_name' does not match any of the expected tags`
- **Phiên E2E tự động (`logs/plugathon-e2e.log`):**
  - `event_id`: `d0dfe898-b406-4003-85bd-269589d44f9e` → `reason=SCHEMA_VALIDATION_FAILED` trên `campus.alerts.dlq`.

### 2.2. Fault 2 (`Q07`) — `MAX_RETRIES_EXCEEDED` DLQ & Phục hồi qua `POST /notifications/{id}/retry`

- **Phiên thu log chuyên sâu (`logs/dlq-fault.log`):**
  1. **Bước tiêm lỗi (`FAIL_CHANNELS=sms`, `MAX_RETRIES=0`):**
     - `alert_id`: `ALT-888`
     - `event_id`: `3e047528-1ace-4b21-8cee-f2e7e9cb9bdb`
     - `correlationId`: `req-fault-dlq-a8a40b`
     - `notification_id`: `91c6e8a5-5230-4fd1-adb9-2032477ef7ed`
     - `created_at`: `2026-11-13T11:47:30Z`
     - Trạng thái ban đầu trong PostgreSQL: `status="failed"`, `sent=false`, `retry_count=0`, `error_detail="sms gateway unavailable (simulated by FAIL_CHANNELS)"`.
     - **Envelope thu trực tiếp từ topic `campus.alerts.dlq` tại `2026-11-13T11:47:30Z`:**
       ```json
       {
         "topic": "campus.alerts.dlq",
         "reason": "MAX_RETRIES_EXCEEDED",
         "error_detail": "sms gateway unavailable (simulated by FAIL_CHANNELS)",
         "retry_count": 0,
         "failed_at": "2026-11-13T11:47:30Z",
         "notification_id": "91c6e8a5-5230-4fd1-adb9-2032477ef7ed",
         "event_id": "3e047528-1ace-4b21-8cee-f2e7e9cb9bdb",
         "alert_id": "ALT-888"
       }
       ```
  2. **Bước phục hồi (`FAIL_CHANNELS=""`, `MAX_RETRIES=3` → `POST /notifications/91c6e8a5-5230-4fd1-adb9-2032477ef7ed/retry`):**
     - HTTP Status: `200 OK`
     - `status`: `"delivered"`, `sent`: `true`, `retry_count`: `1`, `error_detail`: `null`
     - `delivered_at`: `2026-11-13T11:47:38Z`
     - Log container tương ứng trong [logs/api-container.log](logs/api-container.log):
       `logger=notification.delivery channel=sms alert_id=ALT-888 correlationId=req-fault-dlq-a8a40b delivered`
- **Phiên E2E & Demo Walkthrough (`demo/demo_walkthrough.log` & `logs/plugathon-e2e.log`):**
  - `demo_walkthrough.log`: `notification_id=7007d913-170e-4c92-bf7b-a1c70e4339a2` (`ALT-8279`, `correlationId=req-dlq-rec-2132cc`) → `MAX_RETRIES_EXCEEDED` → phục hồi `delivered`, `retry_count=1`.
  - `logs/plugathon-e2e.log`: `notification_id=375a274c-3c46-49c7-abb9-36c8e838b26f` → `MAX_RETRIES_EXCEEDED` → phục hồi `delivered`, `retry_count=1`.

### 2.3. Fault 3 (`Q09`) — Out-of-Order Suppression (`SUPPRESSED_OUT_OF_ORDER`)

- **Phiên thu log chuyên sâu (`logs/dlq-fault.log`, `alert_id=ALT-690`, `correlationId=req-cb-ooo-f78b9c35`):**
  1. `alert.resolved` tới trước: `notification_id=ed118256-1809-4ee4-9143-b6382a62e05f`, `event_id=b2da41d2-bdb6-45d5-9c91-2648cadb249d`, `created_at=2026-11-13T11:47:22Z`, `status="delivered"`, `sent=true`.
  2. `alert.created` trễ hơn 10 phút tới sau: `notification_id=6eb68d0a-cebf-4b6a-8c7e-ad74003d194e`, `event_id=ac2e1e8c-3bbf-4452-af50-4d1de59f2989`, `created_at=2026-11-13T11:47:23Z`.
  3. Kết quả lưu DB: `status="duplicate_ignored"`, `sent=false`, `delivered_at=null`, `error_detail="SUPPRESSED_OUT_OF_ORDER: alert ALT-690 already resolved at 2026-11-13T11:47:22Z (>= 2026-11-13T11:37:22Z)"`.
- **Phiên `ALT-692` trên log container (`logs/api-container.log` & `screenshots/ready-endpoint.png`):**
  - `event_id=07acefde-22ba-4010-a359-218b09e8fbef` (`correlationId=req-cb-ooo-5b297e8f`) → `logger=notification.store suppressed out-of-order event_name=alert.created alert_id=ALT-692 origin=mqtt`.
- **Phiên Newman & E2E:** `ALT-9904` (`32a7dc36-2553-4742-aaaa-59c3d9fe1bf3`) và `ALT-9885` (`fe52fba5-a559-45fc-989d-fb6a2af1a2fb`) đều đạt `duplicate_ignored`.

### 2.4. Fault 4 (`Q05` & REST RFC 9457) — `401`, `422`, `400`, `409`

Trích từ [logs/dlq-fault.log](logs/dlq-fault.log) mục 4:
- **`401 Unauthorized`:** Token sai `"wrong-token"` → `type: "https://campus.local/errors/unauthorized"`, `detail: "Bearer token không hợp lệ"`.
- **`422 Unprocessable Entity`:** `target_channels: ["zalo"]` → `type: "https://campus.local/errors/unprocessable"`, `code: "ENUM_MISMATCH"`.
- **`400 Bad Request`:** `GET /notifications/recent?limit=101` → `type: "https://campus.local/errors/validation"`, `field: "limit"`, `code: "OUT_OF_RANGE"`.
- **`409 Conflict`:** Gửi lại `event_id=3e047528-1ace-4b21-8cee-f2e7e9cb9bdb` → `type: "https://campus.local/errors/duplicate-event"`, chỉ về `notification_id=91c6e8a5-5230-4fd1-adb9-2032477ef7ed` đã xử lý trước đó.

---

## 3. Liên kết tài liệu & bằng chứng liên quan

- Quy trình tiêm lỗi: [docs/fault_injection_runbook.md](../docs/fault_injection_runbook.md)
- Tổng hợp bằng chứng: [evidence/README.md](README.md)
- Ảnh chụp trực tiếp trạng thái DB/API: [screenshots/ready-endpoint.png](screenshots/ready-endpoint.png)
