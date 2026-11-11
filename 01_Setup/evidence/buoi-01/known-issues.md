# Known Issues · Buổi 1

Ghi lại lỗi chưa xử lý được hoặc đã xử lý xong trong quá trình thiết lập môi trường Buổi 1.

| STT | Lỗi gặp phải | Lệnh gây lỗi | Cách đã thử | Trạng thái |
|---:|---|---|---|---|
| 1 | Docker daemon chưa khởi động ở lần kiểm tra đầu tiên (`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`) | `docker info` | Khởi động ứng dụng Docker Desktop, chờ WSL2 engine chuyển sang trạng thái Running và chạy lại kiểm tra | Đã xử lý xong (`[PASS]`) |
