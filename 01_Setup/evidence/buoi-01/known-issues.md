# Known Issues · Buổi 1

Ghi lại lỗi chưa xử lý được hoặc đã xử lý xong trong quá trình thiết lập môi trường Buổi 1.

| STT | Lỗi gặp phải | Lệnh gây lỗi | Cách đã thử | Trạng thái |
|---:|---|---|---|---|
| 1 | Docker daemon chưa khởi động ở lần kiểm tra đầu tiên (`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`) | `docker info` | Khởi động ứng dụng Docker Desktop, chờ WSL2 engine chuyển sang trạng thái Running và chạy lại kiểm tra | Đã xử lý xong (`[PASS]`) |
| 2 | `evidence/buoi-01/git-log.txt` là bản chụp lịch sử tại mốc Lab 01 có hash đầu `efac0ef` không trùng với commit ổn định cuối cùng của Lab 01 trên `main` (`7a40711`) | `git log --oneline -5` (khi tạo snapshot trước lần cập nhật cuối) | Giữ nguyên snapshot lịch sử Buổi 1 (không rewrite git history); đối chiếu lịch sử thực tế bằng `git log --oneline` (`7a40711` đến `5f7ae48`) | Đã ghi nhận minh bạch |
| 3 | `evidence/buoi-01/service-boundary.md` là bản thiết kế ranh giới ban đầu ở Lab 01 (nêu dự kiến `RabbitMQ`/`SQLite`, ví dụ lỗi validation `400`, `403` trên `/notifications/recent`, và bảng auto-routing chưa có `discord`) | Đối chiếu chéo Lab 01 ↔ Lab 03/04/05 | Giữ bản thiết kế Lab 01 làm tài liệu lịch sử; hợp đồng canonical Pair 04 được chốt tại `03_Postman/queue-contract-tests/pair-04-core-notification/event-contract.md` và triển khai thực tế tại `04_Docker/` & `05_Compose/` | Đã đồng bộ ở Lab 03–05 |
| 4 | `01_Setup/.github/workflows/{check-evidence.yml,check-repo.yml}` nằm trong thư mục con nên GitHub Actions của repo portfolio đơn không tự chạy từ đó | Chạy workflow ở cấu trúc single-repo | Giữ làm workflow tham chiếu của Lab 01; CI toàn portfolio được quản lý tại `../.github/workflows/` | Đã ghi nhận |
