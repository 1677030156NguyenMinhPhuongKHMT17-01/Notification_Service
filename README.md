# FIT4110 — Portfolio Học Kỳ (`FIT4110_<MãSinhViên>`)

Repository portfolio cá nhân cho học phần **FIT4110 – Dịch vụ kết nối và Công nghệ nền tảng**, thực hiện theo quy trình một repository duy nhất của **FIT4110 Student Kit**.

## Thông tin sinh viên & Nhóm bài tập lớn

| Trường thông tin | Nội dung |
|---|---|
| **Họ và tên** | Nguyễn Minh Phượng *(hoặc cập nhật tên của bạn)* |
| **Mã sinh viên (MSSV)** | `<MãSinhViên>` *(điền MSSV trước khi push)* |
| **Nhóm** | Nhóm A7 — Product A *(hoặc B7 — Product B)* |
| **Service phụ trách** | **Notification Service** (Dịch vụ gửi cảnh báo đa kênh) |
| **Cặp phụ thuộc (Pairing Matrix)** | **Pair #4: Core Business (A6/B6) → Notification (A7/B7)** (`Queue async`: `alert.created`, `alert.escalated`, `alert.resolved`) + REST API quản trị/kiểm thử |
| **Công nghệ dự kiến** | Python 3.11 + FastAPI, RabbitMQ (`Queue async`), SQLite/PostgreSQL, Telegram Bot API + Console/DB Log |

---

## Cấu trúc Portfolio theo từng Lab

```text
FIT4110_<MãSinhViên>/
├── README.md                 # Tổng quan portfolio học kỳ
├── 01_Setup/                 # Lab 01: Thiết lập môi trường & Xác định Service Boundary
├── 02_OpenAPI/               # Lab 02: Thiết kế hợp đồng (Event Contract & OpenAPI 3.1) + Biên bản đàm phán
├── 03_Postman/               # Lab 03: Kiểm thử tích hợp với Postman, Prism Mock, Newman & Async Contract
├── 04_Docker/                # Lab 04: Đóng gói Notification Service bằng Docker
├── 05_Compose/               # Lab 05: Chạy multi-container stack (API + DB + Queue) bằng Docker Compose
└── 06_Plugathon/             # Lab 06: Kết nối liên service (Plug-a-thon) & Demo Pack cuối kỳ
```

## Danh mục các buổi thực hành

| Buổi / Lab | Thư mục | Nội dung chính | Trạng thái |
|---|---|---|---|
| **Buổi 1 (Lab 01)** | [`01_Setup/`](./01_Setup/) | Kiểm tra toolchain, pull Docker images, chạy smoke test, thu thập minh chứng môi trường (`evidence/buoi-01/`) và đặc tả **Service Boundary** cho **Notification Service** (khớp với `pairing-matrix.md` Pair #4) | Đã hoàn thành |
| **Buổi 2 (Lab 02)** | `02_OpenAPI/` | Đàm phán hợp đồng **Pair #4 (`Core Business → Notification`)**, hoàn thiện Event Contract sơ bộ, `openapi.yaml` 3.1, `negotiation-log.md` và minh chứng Spectral + Prism | Dự kiến |
| **Buổi 3 (Lab 03)** | `03_Postman/` | Xây dựng Postman Collection (`mock` & `local`), Newman report, đặc tả Async/Event và Reliability Checklist | Dự kiến |
| **Buổi 4 (Lab 04)** | `04_Docker/` | Viết `Dockerfile` (non-root, `/health`, `.env`), build image và chạy lại Newman test trên container | Dự kiến |
| **Buổi 5 (Lab 05)** | `05_Compose/` | Viết `docker-compose.yml` kết nối Notification Service với Database & Message Broker (RabbitMQ) và kiểm thử end-to-end | Dự kiến |
| **Buổi 6 (Lab 06)** | `06_Plugathon/` | Tích hợp thực tế với `Core Business Service` (A6/B6), hoàn thiện Demo Pack | Dự kiến |
