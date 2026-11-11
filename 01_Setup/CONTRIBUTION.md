# Team artefact and individual contribution (`CONTRIBUTION.md`)

File này ghi nhận phần đóng góp cá nhân và artefact chung của nhóm cho **Lab 01 (Setup & Service Boundary)** theo chuẩn `FIT4110_Student_Kit`.

## Team information

- **Team:** Nhóm 6 *(hoặc A7 / B7)* — Phụ trách **Notification Service**
- **Service/capability:** **Notification Service** (Dịch vụ gửi cảnh báo đa kênh)
- **Dependency Pair (theo `pairing-matrix.md` & `event-contract-04-core-notification.md`):** **Pair #4: Core Business → Notification Service** (Async qua Topic `campus.alerts` trên MQTT Broker `mqtt://192.168.1.51:1883` + REST fallback `/notifications`)
- **Role:** Consumer nhận sự kiện bất đồng bộ (`alert.created`, `alert.escalated`, `alert.resolved`) từ `Core Business Service`; đồng thời là Provider của REST API `/notifications` (fallback/log query)
- **Members:**
  - Nguyễn Minh Phượng – `<MãSinhViên>`
  - `<Thành viên 2>` – `<MSSV 2>`
  - `<Thành viên 3>` – `<MSSV 3>`
  - `<Thành viên 4>` – `<MSSV 4>`
- **Shared artefacts:** `evidence/buoi-01/service-boundary.md`

## Individual contribution

- **Work completed:**
  - Thiết lập môi trường phát triển cá nhân (Git, Docker Desktop, Docker Compose v2, Node.js, Python).
  - Kéo bộ 14 Docker image tiêu chuẩn (`scripts/pull_all.ps1`), chạy kiểm thử khói (`scripts/smoke_test.ps1`) và thu thập toàn bộ 11 file minh chứng (`scripts/collect_session01_evidence.ps1`).
  - Phân tích và biên soạn tài liệu `evidence/buoi-01/service-boundary.md` cho **Notification Service** đồng bộ chính xác với hợp đồng `event-contract-04-core-notification.md` và thông số của nhóm `Core Business` (Subscribe topic `campus.alerts` tại `mqtt://192.168.1.51:1883`, xử lý 3 event `alert.created`, `alert.escalated`, `alert.resolved` theo convention `snake_case`, idempotent theo `event_id`, retry 3 lần interval 5s, và REST fallback `POST /notifications`, `GET /notifications`).
- **Files or sections owned:**
  - `01_Setup/evidence/buoi-01/*`
  - `01_Setup/CONTRIBUTION.md`
- **Commands or tests run:**
  - `.\scripts\pull_all.ps1`
  - `.\scripts\smoke_test.ps1`
  - `.\scripts\collect_session01_evidence.ps1`
  - `python .\scripts\verify_submission.py`
- **Issues resolved:**
  - Khởi động Docker Desktop WSL2 engine và xác nhận mini-stack (`nginx:8081`, `redis`, `registry:5000`) hoạt động ổn định.
  - Đồng bộ hóa cấu trúc payload `snake_case`, danh sách kênh (`telegram`, `email`, `discord`, `sms`) và thông số MQTT Broker (`mqtt://192.168.1.51:1883`, topic `campus.alerts`) với nhóm Core Business.
- **Remaining limitations:**
  - Không có lỗi tồn đọng trong quá trình chạy smoke test.
- **Corrections made after a deadline, if any:**
  - Không có.

## Agreement check

- [x] Shared artefacts match the agreed team version.
- [x] Personal contribution is described accurately.
- [x] No secret or private data is included.
