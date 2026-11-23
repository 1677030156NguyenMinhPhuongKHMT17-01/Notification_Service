# Checklist Kiểm Tra Trước Khi Nộp Đồ Án — Lab 06 & Toàn Bộ FIT4110

Rà soát theo đúng **7 cổng DemoPack (`05_Assessment/DemoPack.md`)**, **9 mục Checklist tổng (`05_Assessment/Checklist.md`)** và **5 Luật Liên Nhóm**.

> **Ghi chú trung thực:** Các mục `[x]` phản ánh tệp, sơ đồ, slide và **kết quả chạy thực tế đã thu nhận ngày `2026-11-13`** (Docker Compose `3/3` healthy, E2E `13/13 PASS`, Newman `21/21` req / `37/37` assertions `PASS`, Demo `40.9s`). Các mục `[ ]` chỉ giữ cho phần thao tác cuối của sinh viên (thay `<MãSinhViên>`, quay & gắn link video thật, đẩy lên GitHub kiểm tra CI xanh).

---

## 1. Nhận diện & Hồ sơ Sinh viên

- [x] Giữ nguyên thông tin chuẩn hóa: **Nguyễn Minh Phượng**, placeholder **`<MãSinhViên>`**, **Nhóm 6 *(hoặc A7 / B7)* — Notification Service**.
- [ ] *(Thao tác sinh viên trước khi nộp LMS)* Thay `<MãSinhViên>` thành MSSV thật theo yêu cầu giảng viên (trong quá trình phát triển swarm luôn giữ nguyên placeholder).

---

## 2. Cấu trúc Repository & 7 Cổng DemoPack (Mục 11 & `DemoPack.md`)

| Cổng | Hạng mục yêu cầu | Trạng thái | Tệp / Vị trí trong Repo |
| :---: | :--- | :---: | :--- |
| **Gate 1** | `README.md` rõ ràng, mô tả kiến trúc, cài đặt & run | `[x]` | [README.md](../README.md) & [RUN_PLUGATHON.md](../RUN_PLUGATHON.md) |
| **Gate 2** | Frozen Contracts + Changelog + Verification | `[x]` | [contracts/](../contracts/notification.openapi.yaml), [docs/changelog.md](../docs/changelog.md), [scripts/verify_frozen_contracts.py](../scripts/verify_frozen_contracts.py) |
| **Gate 3** | One-Command Startup (`docker compose up -d --build --wait`) | `[x]` | [docker-compose.yml](../docker-compose.yml), [docker-compose.external-broker.yml](../docker-compose.external-broker.yml), [.env.example](../.env.example), [Makefile](../Makefile) |
| **Gate 4** | Sơ đồ Kiến trúc & Triển khai + Presentation Slides | `[x]` | [diagrams/service_boundary.png](../diagrams/service_boundary.png), [diagrams/deployment_diagram.png](../diagrams/deployment_diagram.png), [slides/architecture_presentation.pdf](../slides/architecture_presentation.pdf) |
| **Gate 5** | Runbook Tiêm lỗi, Bằng chứng Log, Screenshot, Newman | `[x]` | [docs/fault_injection_runbook.md](../docs/fault_injection_runbook.md), [evidence/README.md](../evidence/README.md), [evidence/fault_record.md](../evidence/fault_record.md), `evidence/logs/*`, `evidence/screenshots/*`, [reports/newman-plugathon.html](../reports/newman-plugathon.html) (`13/13` E2E, `21/21` req / `37/37` assertions PASS) |
| **Gate 6** | Demo Pack Automation (`run_demo.sh`, `run_demo.ps1`, Script 2–3p) | `[ ]` | Automation & Script xong (`demo/run_demo.ps1` verified `40.9s`, [demo_walkthrough.log](../../demo/demo_walkthrough.log)); giữ `[ ]` trung thực chờ sinh viên tự quay video 2–3 phút và gắn URL thật tại [evidence/demo_video_link.txt](../evidence/demo_video_link.txt) |
| **Gate 7** | Known Issues, Contribution & Individual Reflection | `[x]` | [known-issues.md](../known-issues.md), [CONTRIBUTION.md](../CONTRIBUTION.md), [evidence/reflection/individual_reflection.md](../evidence/reflection/individual_reflection.md) |

---

## 3. Rà soát Clean-Repo Hygiene & 5 Luật Liên Nhóm

- [x] **Không có secret / `.env` / `node_modules` / `__pycache__` được track trong Git** (đã cập nhật `.gitignore`).
- [x] **Không hard-code IP đối tác trong code hoặc ảnh:** Tất cả broker URL dùng `${MQTT_BROKER_URL}` với default an toàn.
- [x] **Không sửa hợp đồng của đối tác:** `contracts/core-business.openapi.yaml` khớp SHA-256 bản gốc từ Lab 05 (`9/9` contracts verified).
- [x] **Sạch sẽ thư mục `diagrams/`:** Chỉ giữ duy nhất `service_boundary.png` và `deployment_diagram.png` (không để sót helper `.html` hay tệp tạm).
- [x] **Liên kết nội bộ hợp lệ:** Toàn bộ đường dẫn tới `docs/`, `diagrams/`, `slides/`, `contracts/`, `checklists/` đều nhất quán.

---

## 4. Các đầu việc cuối trước khi đóng gói nộp bài

- [x] Chạy kiểm chứng thực tế toàn bộ stack Docker Compose (`3/3` healthy, `uid=10001`), E2E `--with-compose-dlq-recovery` (`13/13 PASS`), Newman (`21/21` req, `37/37` assertions, `0` failed, `2.3s`), xuất 3 screenshot (`swagger-ui.png`, `newman-report.png`, `ready-endpoint.png`), 6 tệp log trong `evidence/logs/` và biên bản [evidence/fault_record.md](../evidence/fault_record.md).
- [x] Hoàn tất thư mục `FIT4110_MSSV/demo/` (`video_script_2_3min.md`, `run_demo.sh`, `run_demo.ps1`, `README.md`, `RUN_DEMO.md`), cập nhật `FIT4110_MSSV/README.md` và xác minh walkthrough thực tế `40.9s` ([demo_walkthrough.log](../../demo/demo_walkthrough.log)).
- [ ] *(Sinh viên thực hiện)* Push lên GitHub, kiểm tra workflow `.github/workflows/lab06-plugathon-demo.yml` chạy xanh, quay video 2–3 phút và cập nhật `VIDEO_URL` vào [evidence/demo_video_link.txt](../evidence/demo_video_link.txt).

