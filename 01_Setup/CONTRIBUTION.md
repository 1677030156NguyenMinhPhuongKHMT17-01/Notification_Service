# Team artefact and individual contribution (`CONTRIBUTION.md`)

File này ghi nhận phần đóng góp cá nhân và artefact chung của nhóm cho **Lab 01 (Setup & Service Boundary)** theo chuẩn `FIT4110_Student_Kit`.

## Team information

- **Team:** Nhóm A7 — Product A *(hoặc B7 — Product B)*
- **Service/capability:** **Notification Service** (Dịch vụ gửi cảnh báo đa kênh)
- **Dependency Pair (theo `pairing-matrix.md`):** **Pair #4: Core Business (A6/B6) → Notification (A7/B7)** (`Queue async`)
- **Role:** Provider năng lực gửi thông báo (Event Consumer nhận `alert.created`, `alert.escalated`, `alert.resolved` từ `Core Business Service`; đồng thời cung cấp REST API quản trị/tra cứu và gọi `Telegram Bot API`)
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
  - Phân tích và biên soạn tài liệu `evidence/buoi-01/service-boundary.md` cho **Notification Service** bám sát **Pair #4 (`Core Business → Notification` theo cơ chế Queue async)** trong `pairing-matrix.md` và `pair-04-core-notification-async.md` (xác định Actor, System/Service Boundary, Event Payload & REST Schema, bảng "Ai gọi ai", 3 sự kiện `alert.created` / `alert.escalated` / `alert.resolved` + 5 endpoint REST dự kiến, sơ đồ Mermaid và 6 vấn đề đàm phán cho Buổi 2).
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
  - Đồng bộ hóa kiến trúc Service Boundary của Notification Service với `pairing-matrix.md` (Pair #4 Queue async).
- **Remaining limitations:**
  - Không có lỗi tồn đọng trong quá trình chạy smoke test.
- **Corrections made after a deadline, if any:**
  - Không có.

## Agreement check

- [x] Shared artefacts match the agreed team version.
- [x] Personal contribution is described accurately.
- [x] No secret or private data is included.
