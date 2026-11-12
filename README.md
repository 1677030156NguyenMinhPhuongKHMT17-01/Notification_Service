# FIT4110 — Portfolio Học Kỳ (`FIT4110_<MãSinhViên>`)

Repository portfolio cá nhân cho học phần **FIT4110 – Dịch vụ kết nối và Công nghệ nền tảng**, thực hiện theo quy trình một repository duy nhất của **FIT4110 Student Kit**.

## Thông tin sinh viên & Nhóm bài tập lớn

| Trường thông tin | Nội dung |
|---|---|
| **Họ và tên** | Nguyễn Minh Phượng *(hoặc cập nhật tên của bạn)* |
| **Mã sinh viên (MSSV)** | `<MãSinhViên>` *(điền MSSV trước khi push)* |
| **Nhóm** | Nhóm 6 *(hoặc A7 / B7)* — Phụ trách **Notification Service** |
| **Service phụ trách** | **Notification Service** (Dịch vụ gửi cảnh báo đa kênh) |
| **Cặp phụ thuộc (Pairing Matrix)** | **Pair #4: Core Business → Notification Service** (Async qua MQTT Broker `mqtt://192.168.1.51:1883` / Topic `campus.alerts`: `alert.created`, `alert.escalated`, `alert.resolved` + REST API fallback `/notifications`) |
| **Công nghệ dự kiến** | Python 3.11 + FastAPI, MQTT (`paho-mqtt`) / RabbitMQ, SQLite/PostgreSQL, Telegram Bot API + Email + SMS/Console Mock |

---

## Cấu trúc Portfolio theo từng Lab

```text
FIT4110_<MãSinhViên>/
├── README.md                 # Tổng quan portfolio học kỳ
├── 01_Setup/                 # Lab 01: Thiết lập môi trường & Xác định Service Boundary
├── 02_OpenAPI/               # Lab 02: Thiết kế hợp đồng (Event Contract & OpenAPI 3.1) + Biên bản đàm phán
├── 03_Postman/               # Lab 03: Kiểm thử tích hợp với Postman, Prism Mock, Newman & AsyncAPI
├── 04_Docker/                # Lab 04: Đóng gói Notification Service bằng Docker
├── 05_Compose/               # Lab 05: Chạy multi-container stack (API + DB + Broker) bằng Docker Compose
└── 06_Plugathon/             # Lab 06: Kết nối liên service (Plug-a-thon) & Demo Pack cuối kỳ
```

## Danh mục các buổi thực hành

| Buổi / Lab | Thư mục | Nội dung chính | Trạng thái |
|---|---|---|---|
| **Buổi 1 (Lab 01)** | [`01_Setup/`](./01_Setup/) | Kiểm tra toolchain, pull Docker images, chạy smoke test, thu thập minh chứng môi trường (`evidence/buoi-01/`) và đặc tả **Service Boundary** cho **Notification Service** (đồng bộ 100% với `event-contract-04-core-notification.md`) | Đã hoàn thành |
| **Buổi 2 (Lab 02)** | [`02_OpenAPI/`](./02_OpenAPI/) | Đàm phán hợp đồng **Pair #4 (`Core Business → Notification`)**, hoàn thiện Event Contract, `openapi.yaml` 3.1, `negotiation-log.md` và minh chứng Spectral + Prism | Đã hoàn thành |
| **Buổi 3 (Lab 03)** | [`03_Postman/`](./03_Postman/) | Kiểm thử Hợp đồng Queue Async Pair 04 (`queue-contract-tests/pair-04-core-notification/` với Ajv JSON Schema Draft 2020-12 + Semantic Stub `Q05–Q09`) và bộ kiểm thử Postman/Newman + Prism Mock (`TC01–TC16`) | Đã hoàn thành |
| **Buổi 4 (Lab 04)** | [`04_Docker/`](./04_Docker/) | Đóng gói **Notification Service** (FastAPI + Pydantic v2 + MQTT consumer stub) bằng multi-stage non-root `Dockerfile`, `HEALTHCHECK /health`, `.env.example`, kiểm thử `pytest` (6/6 PASS) và Newman trên container thực tế (`18/18 requests, 33/33 assertions PASS`) | Đã hoàn thành |
| **Buổi 5 (Lab 05)** | `05_Compose/` | Viết `docker-compose.yml` kết nối Notification Service với Database & MQTT/Queue Broker và kiểm thử end-to-end | Dự kiến |
| **Buổi 6 (Lab 06)** | `06_Plugathon/` | Tích hợp thực tế với `Core Business Service` qua MQTT Broker `mqtt://192.168.1.51:1883` (`campus.alerts`), hoàn thiện Demo Pack | Dự kiến |
