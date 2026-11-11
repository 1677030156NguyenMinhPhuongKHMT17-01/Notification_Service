# Reliability Checklist — FIT4110 Lab 03 (Nhóm 6: Notification Service)

Điền checklist này trước khi nộp Lab 03.

## 0. Queue Async Event Contract Testing (Pair 04: `Core Business → Notification`)

- [x] Có `event-contract.md` đồng bộ từ Lab 02 (`campus.alerts`, `mqtt://192.168.1.51:1883`, `snake_case`).
- [x] Có JSON Schema Draft 2020-12 cho cả 3 event (`alert.created.schema.json`, `alert.escalated.schema.json`, `alert.resolved.schema.json`, `campus.alerts.schema.json`).
- [x] Có 06 valid samples (`samples/valid/`) chạy PASS.
- [x] Có 08 invalid samples (`samples/invalid/`) bị schema từ chối (`[PASS expected-invalid]`).
- [x] Có script tự động `scripts/test-event-contract.js` kiểm tra cả Mức A (JSON Schema) và Mức B (Semantic Stub `Q05–Q09`).
- [x] Có báo cáo `reports/event-contract-test.txt`.
- [x] Có ma trận `event-test-matrix.md` (`Q01–Q09` + đặc thù Pair 04) và `producer-consumer-handshake.md` (`READY`).

## 1. Functional tests (REST Fallback & Admin Query API)

- [x] Có test cho endpoint health (`TC01 - GET /health`).
- [x] Có test happy path cho endpoint chính (`TC02 - POST /notifications`).
- [x] Có kiểm tra status code 2xx (`200 OK`, `201 Created`).
- [x] Có kiểm tra field quan trọng trong response (`notification_id`, `event_id`, `alert_id`, `sent`, `status`, `retry_count`).
- [x] Có ít nhất 1 test đọc dữ liệu danh sách hoặc chi tiết (`TC03 - GET /notifications`, `TC04 - GET /notifications/recent`, `TC05 - GET /notifications/{id}`).

## 2. Auth tests

- [x] Có test thiếu token (`TC08 - POST /notifications` không có header `Authorization`, không dùng `Prefer: code=401`).
- [x] Có test sai token hoặc token rỗng (`TC09 - POST /notifications` với `Bearer invalid-token`).
- [x] Endpoint public được khai báo rõ nếu không cần auth (`GET /health` có `security: []`).
- [x] Test thể hiện đúng expected status 401/403.

## 3. Negative tests

- [x] Có test thiếu field bắt buộc (`TC10 - POST /notifications` thiếu `message`).
- [x] Có test sai kiểu dữ liệu / pattern (`TC10` — `alert_id: "BAD_ID"` sai pattern `^ALT-[0-9]{3,6}$`).
- [x] Có test sai enum hoặc giá trị ngoài miền (`TC11 - POST /notifications` với `target_channels: ["zalo"]`).
- [x] Lỗi trả về theo cùng một error model (RFC 9457 `ProblemDetails` — `application/problem+json`).

## 4. Boundary tests

- [x] Có test min/max hoặc dữ liệu sát ngưỡng (`TC12 - POST /notifications` tự định tuyến khi lược bỏ `target_channels` với `severity: "critical"`).
- [x] Có test limit/pagination nếu endpoint có danh sách (`TC13 - GET /notifications/recent?limit=101` vượt ngưỡng `maximum: 100`).
- [x] Có test duplicate `event_id` idempotency (`TC14 - POST /notifications` trả `409 Conflict`).
- [x] Có ghi chú kỳ vọng xử lý dữ liệu biên.

## 5. Reliability tests cơ bản

- [x] Có kiểm tra response time (`TC16 - POST /notifications` kiểm tra `< 1000ms` trên môi trường `local`).
- [x] Có mô tả timeout mong muốn (REST timeout `<= 1000ms`, cổng gửi ngoài timeout `5000ms`).
- [x] Có test hoặc ghi chú retry/idempotency (`TC06 - POST /notifications/{id}/retry`, `TC14` dedupe theo `event_id`, và `Q05–Q07` trong Queue Async).
- [x] Có consumer-side smoke test với ít nhất 1 mock của nhóm khác (`TC15 - GET {{coreBusinessMockUrl}}/alerts/{alertId}` gọi sang Core Business Mock Server ở cổng `4011`).

## 6. Evidence

- [x] Collection export JSON (`postman/collections/FIT4110_lab03_notification.postman_collection.json`).
- [x] Environment mock export JSON (`postman/environments/FIT4110_lab03_mock.postman_environment.json`).
- [x] Environment local export JSON (`postman/environments/FIT4110_lab03_local.postman_environment.json`).
- [x] Newman report XML/HTML (`reports/newman-report.xml`, `reports/newman-report.html`).
- [x] Test-case matrix đã điền (`templates/test-case-matrix.csv` và `queue-contract-tests/pair-04-core-notification/event-test-matrix.md`).
- [x] Biên bản handshake đã điền (`templates/consumer-provider-handshake.md` và `queue-contract-tests/pair-04-core-notification/producer-consumer-handshake.md`).
