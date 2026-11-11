# FIT4110 — Portfolio Học Kỳ (`FIT4110_<MãSinhViên>`)

Repository portfolio cá nhân cho học phần **FIT4110 – Dịch vụ kết nối và Công nghệ nền tảng**, thực hiện theo quy trình một repository duy nhất của **FIT4110 Student Kit**.

## Thông tin sinh viên & Nhóm bài tập lớn

| Trường thông tin | Nội dung |
|---|---|
| **Họ và tên** | Nguyễn Minh Phượng *(hoặc cập nhật tên của bạn)* |
| **Mã sinh viên (MSSV)** | `<MãSinhViên>` *(điền MSSV trước khi push)* |
| **Nhóm** | Nhóm A7 — Product A *(hoặc B7 — Product B)* |
| **Service phụ trách** | **Notification Service** (Dịch vụ gửi cảnh báo đa kênh) |
| **Vai trò của Service** | Downstream Consumer của `Core Business Service`, Provider log thông báo cho `Analytics Service` |
| **Công nghệ dự kiến** | Python 3.11 + FastAPI, SQLite/PostgreSQL, Telegram Bot API + Console/DB Log |

---

## Cấu trúc Portfolio theo từng Lab

```text
FIT4110_<MãSinhViên>/
├── README.md                 # Tổng quan portfolio học kỳ
├── 01_Setup/                 # Lab 01: Thiết lập môi trường & Xác định Service Boundary
├── 02_OpenAPI/               # Lab 02: Thiết kế hợp đồng API (Contract-first) & Biên bản đàm phán
├── 03_Postman/               # Lab 03: Kiểm thử tích hợp với Postman, Prism Mock & Newman
├── 04_Docker/                # Lab 04: Đóng gói Notification Service bằng Docker
├── 05_Compose/               # Lab 05: Chạy multi-container stack bằng Docker Compose
└── 06_Plugathon/             # Lab 06: Kết nối liên service (Plug-a-thon) & Demo Pack cuối kỳ
```

## Danh mục các buổi thực hành

| Buổi / Lab | Thư mục | Nội dung chính | Trạng thái |
|---|---|---|---|
| **Buổi 1 (Lab 01)** | [`01_Setup/`](./01_Setup/) | Kiểm tra toolchain, pull Docker images, chạy smoke test, thu thập minh chứng môi trường (`evidence/buoi-01/`) và đặc tả **Service Boundary** cho **Notification Service** | Đã hoàn thành |
| **Buổi 2 (Lab 02)** | `02_OpenAPI/` | Thiết kế `openapi.yaml` 3.1, Endpoint Catalog và biên bản chốt API với nhóm `Core Business` & `Analytics` | Dự kiến |
| **Buổi 3 (Lab 03)** | `03_Postman/` | Xây dựng Postman Collection (`mock` & `local`), Newman report và Reliability Checklist | Dự kiến |
| **Buổi 4 (Lab 04)** | `04_Docker/` | Viết `Dockerfile` (non-root, `/health`, `.env`), build image và chạy lại Newman test trên container | Dự kiến |
| **Buổi 5 (Lab 05)** | `05_Compose/` | Viết `docker-compose.yml` kết nối Notification API với Database/Queue và kiểm thử end-to-end | Dự kiến |
| **Buổi 6 (Lab 06)** | `06_Plugathon/` | Tích hợp thực tế với `Core Business Service` & `Analytics Service`, hoàn thiện Demo Pack | Dự kiến |
