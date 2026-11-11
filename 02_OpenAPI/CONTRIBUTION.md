# Team artefact and individual contribution (`CONTRIBUTION.md`)

File này ghi nhận phần đóng góp cá nhân và artefact chung của nhóm cho **Lab 02 (Contract-First: Event Contract & OpenAPI 3.1)** theo chuẩn `FIT4110_Student_Kit`.

## Team information

- **Team:** Nhóm 6 *(hoặc A7 / B7)* — Phụ trách **Notification Service**
- **Service/capability:** **Notification Service** (Dịch vụ gửi cảnh báo đa kênh)
- **Dependency Pair:** **Pair #4: Core Business → Notification Service** (Async qua MQTT Broker `mqtt://192.168.1.51:1883` / Topic `campus.alerts` + REST fallback `/notifications`)
- **Role:** Both (Event Consumer nhận `alert.created`, `alert.escalated`, `alert.resolved` từ `Core Business Service`; REST API Provider cho `/notifications`)
- **Members:**
  - Nguyễn Minh Phượng – `<MãSinhViên>`
  - `<Thành viên 2>` – `<MSSV 2>`
  - `<Thành viên 3>` – `<MSSV 3>`
  - `<Thành viên 4>` – `<MSSV 4>`
- **Shared artefacts:**
  - `event-contract-04-core-notification.md` & `docs/event-contract-template.md`
  - `openapi.yaml`
  - `negotiation-log.md`
  - `docs/analysis-provider.md` & `docs/analysis-consumer.md`
  - `VERSIONING.md`

## Individual contribution

- **Work completed:**
  - Đồng bộ hợp đồng sự kiện bất đồng bộ **Pair #4 (`Core Business → Notification Service`)** trong `event-contract-04-core-notification.md` và `docs/event-contract-template.md` (MQTT Broker `mqtt://192.168.1.51:1883`, topic `campus.alerts`, 3 sự kiện `alert.created`, `alert.escalated`, `alert.resolved` theo convention `snake_case`).
  - Thiết kế đặc tả `openapi.yaml` chuẩn **OpenAPI 3.1.0** cho Notification Service (gồm `/health`, `/notifications`, `/notifications/recent`, `/notifications/{notification_id}`, `webhooks`, `oneOf` + `discriminator` theo `event_name`, union type `[string, 'null']` cho `error_detail`, và `Problem Details` RFC 9457).
  - Hoàn thiện `docs/analysis-provider.md`, `docs/analysis-consumer.md`, `negotiation-log.md` (6 issues) và `VERSIONING.md`.
  - Chạy kiểm tra `spectral lint` với `campus-spectral.yaml`, khởi chạy Prism mock server tại `http://localhost:4010` và kiểm thử 5 request mẫu bằng `curl` (3 happy path + 2 error case).
- **Files or sections owned:**
  - `02_OpenAPI/openapi.yaml`
  - `02_OpenAPI/event-contract-04-core-notification.md`
  - `02_OpenAPI/docs/*`
  - `02_OpenAPI/negotiation-log.md`
  - `02_OpenAPI/VERSIONING.md`
  - `02_OpenAPI/evidence/buoi-02/*`
- **Commands or tests run:**
  - `.\scripts\install_lab02_cli.ps1`
  - `.\scripts\lint_openapi.ps1`
  - `.\scripts\collect_session02_evidence.ps1`
  - `.\scripts\test_mock_with_curl.ps1`
- **Issues resolved:**
  - Thống nhất quy ước `snake_case` kèm trường `correlationId`, giá trị `severity` chữ thường (`low`, `medium`, `high`, `critical`) và cơ chế retry 3 lần (interval 5s) với nhóm Core Business.
  - Xử lý triệt để toàn bộ cảnh báo Spectral (`0 errors, 0 warnings`).
- **Remaining limitations:**
  - Không có lỗi tồn đọng.
- **Corrections made after a deadline, if any:**
  - Không có.

## Agreement check

- [x] Shared artefacts match the agreed team version.
- [x] Personal contribution is described accurately.
- [x] No secret or private data is included.

