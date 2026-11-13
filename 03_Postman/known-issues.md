# Known Issues — Lab 03 (Contract & Newman/Prism Testing)

Tài liệu ghi nhận các điểm lệch đã đối soát giữa đặc tả REST tĩnh, bộ kiểm thử Queue Async canonical Pair #04 và môi trường giả lập Prism/Newman tại `03_Postman/`.

## 1. Đối soát `contracts/notification.openapi.yaml` với Canonical Pair #04 (`event-contract.md`)

Khi đối chiếu `contracts/notification.openapi.yaml` với hợp đồng sự kiện chuẩn tại `queue-contract-tests/pair-04-core-notification/event-contract.md` (và các JSON Schema Draft 2020-12 trong `queue-contract-tests/pair-04-core-notification/schema/`), các sai lệch trước đây đã được chuẩn hóa như sau:

| Hạng mục | Trước đối soát | Chuẩn canonical sau cập nhật | Lý do / Tương thích |
|---|---|---|---|
| `alert_id` pattern | `^ALT-[0-9]{3,6}$` | `^ALT-[0-9]{3,}$` | Cho phép mã cảnh báo >= 3 chữ số (không chặn >= 7 chữ số), khớp `event-contract.md` và JSON Schema. |
| `correlationId` | `minLength: 4` | `minLength: 1` | Khớp schema chuẩn cho các mã truy vết ngắn vẫn hợp lệ (`minLength: 1`). |
| `AlertEscalatedEvent` | `escalation_level` `1..10`, thiếu `severity`, `message` | `escalation_level` `1..5`, bổ sung optional `severity` và `message` (`5..500`) | Đồng bộ chính xác với `alert.escalated.schema.json`. |
| `AlertResolvedEvent` | Thiếu `target_channels` | Bổ sung optional `target_channels` | Đồng bộ với `alert.resolved.schema.json`. |
| `NotificationLog.severity` | Chỉ nhận `SeverityLevel` (không cho `null`) | `oneOf: [$ref: SeverityLevel, type: 'null']` | Hỗ trợ bản ghi event không gắn `severity` theo chuẩn OpenAPI 3.1 (vẫn tuân thủ cấm `nullable: true` của Spectral). |
| `NotificationLog.retry_count` | `minimum: 0`, `maximum: 3` | `minimum: 0` (bỏ `maximum: 3`) | Auto-retry vẫn tối đa 3 lần (interval 5s), nhưng API thực tế có endpoint manual `/retry` làm `retry_count` có thể vượt 3. |
| `GET /health` & `GET /notifications/recent` | `/health` thiếu `503`; `/notifications/recent` có `403` thừa | `/health` bổ sung `503 ServiceUnavailable`; gỡ `403` khỏi `/notifications/recent` (thay `Forbidden` bằng `ServiceUnavailable` trong `components.responses`) | Khớp chính xác tập mã phản hồi chuẩn và không để schema/response dư thừa. |
| `SEVERITY_ROUTING` | Thiếu `discord` ở `high`/`critical` và `email` ở `medium` (ở tài liệu Lab 02) | `low: [email]`, `medium: [telegram, email]`, `high: [telegram, email, discord]`, `critical: [telegram, email, discord, sms]` | Đã đồng bộ trong `02_OpenAPI/docs/analysis-provider.md` & `analysis-consumer.md`. |

## 2. Hợp đồng Partner (`contracts/core-business.openapi.yaml`) là Read-Only

- File `contracts/core-business.openapi.yaml` thuộc sở hữu của nhóm **Core Business Service** (Provider/Producer của Pair #04) và được giữ ở chế độ **chỉ đọc (`read-only`)** để làm đặc tả tham chiếu khi chạy `npm run mock:core` (cổng `4011`).
- Nếu Spectral báo `warning` trên quy ước style riêng của partner spec (nếu có), `npm run lint:contracts` dùng cờ `--fail-severity error` nên vẫn pass (`0 errors`). Không tự ý sửa nội dung hợp đồng thuộc quyền sở hữu của nhóm đối tác.

## 3. Lưu ý môi trường Prism Mock vs Local Container

- **Prism Mock (`http://localhost:4010`, `FIT4110_lab03_mock.postman_environment.json`):**
  - Prism phản hồi giả lập theo ví dụ và schema OpenAPI nên mang tính **stateless**: một bản ghi gửi qua `POST /notifications` sẽ không tự xuất hiện khi gọi lại `GET /notifications` hoặc `GET /notifications/{notification_id}` (chỉ trả dữ liệu mẫu hợp lệ theo schema).
  - Tham số xác thực `Authorization: Bearer ...` trên Prism được kiểm tra theo security scheme OpenAPI (có header hợp lệ định dạng), chưa thực thi xác thực token thực tế hay kiểm tra kết nối PostgreSQL / MQTT như container trong `04_Docker/` và `05_Compose/`.
- **Local Service (`http://localhost:8000`, `FIT4110_lab03_local.postman_environment.json`):**
  - Chạy khi Notification Service thực tế đang mở cổng `8000`. Ở Lab 04–05, service bổ sung thêm các endpoint vận hành (`POST /notifications/{notification_id}/retry`, `GET /ready`) trên nền hợp đồng REST v1.0 đã kiểm thử tại đây.

## 4. Quản lý file Collection, Reports trùng lặp và Scripts hỗ trợ

- **Collection & Environment song song:**
  - Bộ artifact chính dùng trong `package.json`, `scripts/run-newman.sh` và CI là `postman/collections/FIT4110_lab03_notification.postman_collection.json` cùng `FIT4110_lab03_{mock,local}.postman_environment.json`.
  - Các bản `team-notify.postman_collection.json` và `team-notify_{mock,local}.postman_environment.json` được giữ lại làm bí danh tham chiếu theo danh sách ở `README.md` và `checklists/submission_checklist.md`.
- **Dọn report trùng lặp:**
  - Đã xóa `reports/newman-report-mock.xml` vì là bản sao trùng lặp nội dung với `reports/newman-report.xml` và không được tham chiếu ở script hay CI nào. Các file report chính thức tại `reports/` là `contract-lint-report.txt`, `newman-report.xml` và `newman-report.html`.
- **Sửa `Makefile` & `scripts/*.sh`:**
  - Đã thay các target cũ từ starter (`mock:iot`, `mock:vision`, `openapi.yaml`, `FIT4110_lab03_starter.postman_collection.json`) bằng target/đường dẫn đúng của Notification Service (`mock-notify`, `mock-core`, `mock-all`, `test-queue`, `contracts/notification.openapi.yaml`, `contracts/core-business.openapi.yaml`, `FIT4110_lab03_notification.postman_collection.json`).
- **Workflow CI trong portfolio hợp nhất:**
  - `03_Postman/.github/workflows/newman.yml` là mẫu workflow khi chạy Lab 03 như một repository độc lập; trong portfolio hợp nhất `FIT4110_<MãSinhViên>/`, GitHub Actions kích hoạt các workflow đặt tại `.github/workflows/` ở thư mục gốc.
