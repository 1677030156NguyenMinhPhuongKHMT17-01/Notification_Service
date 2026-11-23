# Team Contribution Matrix — Lab 06 Plug-a-thon (Nhóm 6 / A7 / B7)

Báo cáo đóng góp thành viên cho giai đoạn **Lab 06 — Plug-a-thon & Demo Pack** (theo mẫu `team-contribution-template.md` và Mục 9 tài liệu đồ án FIT4110).

## Thông tin Nhóm & Sinh viên

| Hạng mục | Giá trị |
| :--- | :--- |
| **Môn học** | FIT4110 — Dịch vụ kết nối và Công nghệ nền tảng |
| **Họ và tên sinh viên** | Nguyễn Minh Phượng |
| **Mã sinh viên** | `<MãSinhViên>` |
| **Nhóm / Dịch vụ** | **Nhóm 6 *(hoặc A7 / B7)* — Notification Service** |
| **Cặp tích hợp chính** | **Pair 04:** Core Business (`Nhóm 5 / A6 / B6`) → Notification Service (`Nhóm 6 / A7 / B7`) |

---

## Bảng phân công vai trò & Đầu việc cụ thể (4 Vai trò chuẩn FIT4110)

| STT | Vai trò chuẩn (FIT4110 Sec. 9) | Người phụ trách | Phạm vi & Sản phẩm hoàn thành trong Lab 06 |
| :---: | :--- | :--- | :--- |
| **1** | **Service Lead** | Nguyễn Minh Phượng (`<MãSinhViên>`) | Quản lý tiến độ Lab 06, rà soát ranh giới dịch vụ ([docs/service_boundary.md](docs/service_boundary.md)), tổng hợp Demo Pack, slide trình bày ([slides/architecture_presentation.html](slides/architecture_presentation.html), [slides/architecture_presentation.pdf](slides/architecture_presentation.pdf)), `known-issues.md`, phản tư cá nhân (`evidence/reflection/individual_reflection.md`) và rà soát checklist nộp bài. |
| **2** | **API / Contract Owner** | Nguyễn Minh Phượng (`<MãSinhViên>`) | Đóng băng nguyên vẹn **9 tệp hợp đồng** vào `contracts/`, triển khai `scripts/verify_frozen_contracts.py` (SHA-256 `9/9`), bảo đảm `0` lỗi Spectral lint OpenAPI 3.1.0, hoàn thiện `docs/endpoint_catalog.md`, `docs/changelog.md` và `docs/integration_notes.md` cho Core Business / Analytics. |
| **3** | **Backend Developer** | Nguyễn Minh Phượng (`<MãSinhViên>`) | Duy trì & đóng gói runtime **Notification Service** (`../05_Compose/src/notification_app/`: FastAPI, Pydantic v2, PostgreSQL 15 `event_id UNIQUE`, `MqttConsumer` + `ThreadPoolExecutor=4`, `Q09 SUPPRESSED_OUT_OF_ORDER`, auto-retry & DLQ, opt-in webhook Discord/Telegram); xây dựng `scripts/core_business_simulator.py`. |
| **4** | **Test & DevOps Owner** | Nguyễn Minh Phượng (`<MãSinhViên>`) | Thiết lập `docker-compose.yml` + overlay `docker-compose.external-broker.yml` (`class-net`, alias `notification-service`), `.env.example`, `Makefile`, `RUN_PLUGATHON.md`, `docs/fault_injection_runbook.md`, E2E harness `scripts/run_plugathon_e2e.py`, Postman/Newman (`21` requests / `37` assertions), CI `.github/workflows/lab06-plugathon-demo.yml`, sơ đồ triển khai & bằng chứng kiểm thử (`evidence/`). |

---

## Xác nhận trung thực

Toàn bộ mã nguồn, hợp đồng, hạ tầng Compose, kiểm thử tự động và tài liệu trong `FIT4110_MSSV/06_Plugathon/` được thực hiện, kiểm chứng và rà soát nhất quán với các giai đoạn `01_Setup` → `05_Compose` của đồ án, không tự ý sửa đổi hợp đồng đối tác (`core-business.openapi.yaml`) và không đưa thông tin nhạy cảm vào lịch sử Git.

