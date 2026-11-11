# Consumer–Provider Handshake (REST Smoke & Queue Async Overview)

> Lưu ý: Biên bản Handshake chi tiết cho luồng chính **Queue Async (Pair 04: `Core Business → Notification Service` trên topic `campus.alerts`)** được đặt tại [producer-consumer-handshake.md](file:///e:/HT/Nam4_HK1/DichVuKetNoiVaCongNgheNenTang/FIT4110_MSSV/03_Postman/queue-contract-tests/pair-04-core-notification/producer-consumer-handshake.md). File này ghi nhận phần Consumer-side Smoke Test qua REST Mock Server (`core-business.openapi.yaml`) và REST Fallback (`notification.openapi.yaml`).

## Thông tin chung

- **Lab:** FIT4110 Lab 03
- **Ngày:** 2026-08-27
- **Provider team:** Nhóm 5 — Core Business
- **Consumer team:** Nhóm 6 — Notification Service
- **Provider service:** `core-business` (`contracts/core-business.openapi.yaml`)
- **Consumer service:** `notification-service` (`contracts/notification.openapi.yaml`)

## Contract

- **Queue Async Contract (Primary):** `queue-contract-tests/pair-04-core-notification/event-contract.md` (MQTT Broker `mqtt://192.168.1.51:1883`, topic `campus.alerts`)
- **REST Provider Contract file:** `contracts/core-business.openapi.yaml`
- **Mock base URL (Core Business):** `http://localhost:4011` (`{{coreBusinessMockUrl}}`)
- **Mock base URL (Notification Service):** `http://localhost:4010` (`{{baseUrl}}`)
- **Auth method:** `Bearer <token>` (`Authorization: Bearer {{authToken}}`)
- **Endpoint được test (Consumer Smoke `TC15`):** `GET /alerts/{alertId}`

## Smoke test (`TC15`)

### Request

```http
GET /alerts/0196fb3d-4ad7-7d1e-9f49-5d5148d2babc
Authorization: Bearer lab-token
Accept: application/json
```

### Expected response (`200 OK`)

```json
{
  "id": "0196fb3d-4ad7-7d1e-9f49-5d5148d2babc",
  "sourceService": "core-business",
  "alertType": "UNAUTHORIZED_ACCESS",
  "severity": "HIGH",
  "message": "Phát hiện truy cập trái phép tại cổng chính",
  "relatedEventId": "0196fb3d-4ad7-7d1e-9f49-5d5148d2babc",
  "status": "OPEN",
  "createdAt": "2026-05-10T08:00:00Z",
  "resolvedAt": null
}
```

## Kết quả

- [x] Consumer gọi mock thành công (`200 OK` từ `http://localhost:4011/alerts/0196fb3d-4ad7-7d1e-9f49-5d5148d2babc`).
- [x] Consumer parse được field cần dùng (`id`, `sourceService`, `severity`, `status`, `message`).
- [x] Consumer hiểu lỗi 4xx/5xx provider trả về (RFC 9457 `ProblemDetails` — `application/problem+json`).
- [x] Có Newman report (`reports/newman-report.xml`, `reports/newman-report.html`) và Event Contract report (`queue-contract-tests/pair-04-core-notification/reports/event-contract-test.txt`).

## Ghi chú thay đổi hợp đồng

| Nội dung | Trước | Sau | Người đồng ý |
|---|---|---|---|
| Quy ước tên trường Queue `campus.alerts` | Envelope lồng nhau (`data.*`, `camelCase`) | Cấu trúc phẳng `snake_case` (`event_id`, `event_name`, `correlationId`, `source`, `alert_id`, `severity`, `message`, `target_channels`, `timestamp`) | Nhóm 5 (Core Business) & Nhóm 6 (Notification) |
| Thông số MQTT Broker lớp học | Chưa xác định IP | `mqtt://192.168.1.51:1883` (Anonymous), topic `campus.alerts`, DLQ `campus.alerts.dlq` | Nhóm 5 (Core Business) & Nhóm 6 (Notification) |
| Endpoint REST retry thủ công | Chưa tách endpoint riêng | Bổ sung `POST /notifications/{notification_id}/retry` trong `notification.openapi.yaml` | Nhóm 6 (Notification) |

## Xác nhận

- **Provider representative (Nhóm 5 — Core Business):** Đại diện Nhóm Core Business (Signed-off)
- **Consumer representative (Nhóm 6 — Notification Service):** `<Họ tên / MSSV>` (Signed-off — `READY`)
