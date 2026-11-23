# Known Issues & Contract Discrepancies — Notification Service (Nhóm 6 / A7 / B7)

Nhật ký minh bạch các vấn đề đã xử lý, giới hạn kỹ thuật hiện tại và chênh lệch hợp đồng ghi nhận từ `01_Setup` đến `06_Plugathon` (theo mẫu `known-issues-template.md` và **Luật 2 / Luật 5**).

---

## 1. Sai lệch Hợp đồng & Thương lượng liên nhóm

| ID | Thành phần / Nguồn | Mô tả vấn đề | Tác động Pair 04 | Trạng thái & Cách xử lý |
| :--- | :--- | :--- | :--- | :--- |
| **KI-01** | `contracts/core-business.openapi.yaml` (L47) | File OpenAPI v1.0.0 do đối tác **Core Business (Nhóm 5 / A6 / B6)** cung cấp còn giữ giá trị ví dụ `service: lab02-contract-template` tại `/health` và dùng `camelCase` cho entity REST `Alert` nội bộ. | Không gây vỡ Pair 04 vì bus MQTT Pair 04 đã thống nhất phẳng (`snake_case` + `correlationId`) tại `event-contract.md`. | **Open (Upstream read-only):** Nhóm 6 giữ nguyên file đối tác (chỉ đọc, tuân thủ Luật 1 & 2) và phản ánh lại cho Nhóm 5. |
| **KI-02** | Nháp `01_Setup` vs `03_Postman` & `05_Compose` | Bản nháp `01_Setup` từng ghi `high → [telegram, email]` (thiếu `discord`), lẫn mã lỗi `400` cho validation body, và đặt nhãn đối tác theo mã phòng (`A6/B6`–`A7/B7`) thay vì `Nhóm 5`–`Nhóm 6`. | Đã thống nhất hoàn toàn từ Issue #7 Lab 02 → Lab 06 (`high → [telegram, email, discord]`, `422` cho body schema, `400` cho query constraint/JSON lỗi, ghi cả hai cách gọi nhóm `Nhóm 6 / A7 / B7`). | **Resolved** trong `02_OpenAPI/negotiation-log.md` (Issue #7) và `06_Plugathon/docs/service_boundary.md`. |
| **KI-03** | `alert.escalated` & `alert.resolved` optional fields | Hợp đồng cũ chưa thể hiện rõ các trường tùy chọn `severity`, `message`, `target_channels` trên `alert.escalated` và `target_channels` trên `alert.resolved`. | Producer có thể gửi kèm `severity`/`message` khi leo thang hoặc chỉ định `target_channels` lúc đóng sự cố. | **Resolved** trong Draft 2020-12 schema & `models.py` (`NotificationLog.severity` hỗ trợ nullable). |

---

## 2. Giới hạn Kỹ thuật & Ràng buộc Vận hành (Lab 06)

| ID | Hạng mục | Chi tiết & Lý do thiết kế | Biện pháp giảm thiểu / Hướng mở rộng |
| :--- | :--- | :--- | :--- |
| **KI-04** | **Email & SMS đang chạy dạng stdout mock** | Dự án trường học không triển khai SMTP server hay SMS Gateway trả phí; chỉ Discord và Telegram có adapter webhook HTTPS thật opt-in trong `delivery.py`. | Xuất structured stdout log đầy đủ (`alert_id`, `correlationId`, channel) để phục vụ kiểm chứng; dễ dàng gắn SMTP/Twilio adapter mà không đổi API/contract. |
| **KI-05** | **Mosquitto broker dev dùng chế độ anonymous** | `../05_Compose/mosquitto/config/mosquitto.conf` bật `allow_anonymous true` để mọi nhóm dễ ghép trong LAN lớp (`192.168.1.51:1883`). | Phù hợp môi trường Plug-a-thon LAN nội bộ; khi lên production cần bật TLS + ACL + username/password trên broker. |
| **KI-06** | **Bearer Token tĩnh đơn giản (`AUTH_TOKEN`)** | Xác thực `/notifications*` sử dụng single static Bearer token từ biến môi trường (`AUTH_TOKEN`) thay vì OAuth2/JWT JWKS. | Giữ secrets ngoài Git qua `.env`; phù hợp phạm vi Pair 04 & Newman test, có thể nâng cấp middleware JWT sau. |
| **KI-07** | **Thử nghiệm live trên LAN lớp (`192.168.1.51`) & Video Demo** | Chạy local `docker-compose.external-broker.yml` chỉ ghép được với broker thật của lớp khi có mặt trong phòng thực hành; URL video cần sinh viên tự quay & dán link. | Cung cấp đầy đủ overlay compose, simulator giả lập Core Business và kịch bản Demo Pack (`../../demo/`) để trình diễn cả offline lẫn LAN Plug-a-thon; giữ placeholder trung thực tại `evidence/demo_video_link.txt`. |

