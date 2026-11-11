# Known Issues — Lab 02

Ghi các lỗi phát sinh và cách xử lý trong quá trình thực hiện Lab 02.

| Lỗi | Ảnh hưởng | Cách xử lý dự kiến | Người phụ trách |
|---|---|---|---|
| Starter repo gốc thiếu file `VERSIONING.md` trong khi `.github/workflows/check-lab02.yml` kiểm tra `test -f VERSIONING.md` | Có thể làm fail CI nếu không tạo thêm file `VERSIONING.md` | Đã biên soạn và bổ sung đầy đủ `VERSIONING.md` tại thư mục gốc của Lab 02 | Nguyễn Minh Phượng (`<MãSinhViên>`) — Đã xử lý xong |
| Khác biệt quy ước đặt tên trường giữa Core Business (`camelCase`) và Notification (`snake_case`) | Nguy cơ lỗi parse JSON khi nhận message từ topic `campus.alerts` | Đã đàm phán và chốt trong `event-contract-04-core-notification.md`: dùng `snake_case` cho các trường sự kiện và giữ nguyên `correlationId` | Nhóm Core Business & Nhóm 6 (Notification) — Đã xử lý xong |
