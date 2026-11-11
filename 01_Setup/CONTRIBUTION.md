# Team artefact and individual contribution (`CONTRIBUTION.md`)

File này ghi nhận phần đóng góp cá nhân và artefact chung của nhóm cho **Lab 01 (Setup & Service Boundary)** theo chuẩn `FIT4110_Student_Kit`.

## Team information

- **Team:** Nhóm A7 — Product A *(hoặc B7 — Product B)*
- **Service/capability:** **Notification Service** (Dịch vụ gửi cảnh báo đa kênh)
- **Role:** Both (Provider cho `Core Business Service` & `Analytics Service`; Consumer của `Telegram Bot API`)
- **Members:**
  - Nguyễn Minh Phượng – `<MãSinhViên>`
  - `<Thành viên 2>` – `<MSSV 2>`
  - `<Thành viên 3>` – `<MSSV 3>`
  - `<Thành viên 4>` – `<MSSV 4>`
- **Shared artefacts:** `evidence/buoi-01/service-boundary.md`

## Individual contribution

- **Work completed:**
  - Thiết lập môi trường phát triển cá nhân (Git, Docker Desktop, Docker Compose v2, Node.js, Python).
  - Kéo bộ Docker image tiêu chuẩn (`scripts/pull_all.ps1`), chạy kiểm thử khói (`scripts/smoke_test.ps1`) và thu thập toàn bộ 11 file minh chứng (`scripts/collect_session01_evidence.ps1`).
  - Phân tích và biên soạn tài liệu `evidence/buoi-01/service-boundary.md` cho **Notification Service** (xác định Actor, System/Service Boundary, Input/Output schema, bảng "Ai gọi ai", danh sách endpoint dự kiến, sơ đồ Mermaid và 6 vấn đề đàm phán API cho Buổi 2).
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
- **Remaining limitations:**
  - Không có lỗi tồn đọng trong quá trình chạy smoke test.
- **Corrections made after a deadline, if any:**
  - Không có.

## Agreement check

- [x] Shared artefacts match the agreed team version.
- [x] Personal contribution is described accurately.
- [x] No secret or private data is included.

