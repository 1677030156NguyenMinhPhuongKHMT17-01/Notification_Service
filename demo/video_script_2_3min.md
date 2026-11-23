# Kịch bản Video Demo 2–3 Phút (Tổng thời lượng: 02:45)

Kịch bản chuẩn cho video thuyết minh cuối kỳ **FIT4110 — Notification Service (Nhóm 6 · Pair 04)**, khớp 1-1 với lệnh tự động [`run_demo.ps1`](./run_demo.ps1) / [`run_demo.sh`](./run_demo.sh) và các minh chứng trong [`06_Plugathon/`](../06_Plugathon/).

- **Người trình bày:** Nguyễn Minh Phượng (`<MãSinhViên>`) — Nhóm 6 *(hoặc A7 / B7)*
- **Thời lượng mục tiêu:** `02:45` (nằm trong khung bắt buộc 2–3 phút)
- **File lưu link sau khi quay xong:** [`06_Plugathon/evidence/demo_video_link.txt`](../06_Plugathon/evidence/demo_video_link.txt)

---

## Checklist chuẩn bị trước khi bấm Record

1. Đảm bảo Docker Desktop đang chạy và cổng `8000` / `1883` / `5432` đang trống (`docker ps` rỗng hoặc đã `down -v`).
2. Chuẩn bị 3 cửa sổ sẵn sàng để chuyển tab mượt:
   - **Tab 1 (Slide/Diagram):** Mở [`06_Plugathon/slides/architecture_presentation.html`](../06_Plugathon/slides/architecture_presentation.html) hoặc ảnh [`service_boundary.png`](../06_Plugathon/diagrams/service_boundary.png) & [`deployment_diagram.png`](../06_Plugathon/diagrams/deployment_diagram.png).
   - **Tab 2 (Terminal):** Đang ở thư mục gốc `FIT4110_<MãSinhViên>` (kiểm tra font chữ lớn dễ đọc, **không** chứa token thật của Telegram/Discord).
   - **Tab 3 (Browser):** Sẵn sàng mở `http://127.0.0.1:8000/docs`, `http://127.0.0.1:8000/ready` và [`06_Plugathon/reports/newman-plugathon.html`](../06_Plugathon/reports/newman-plugathon.html).
3. Chạy thử một lần trước để Docker cache sẵn image (giúp lần quay thật chạy xong toàn bộ demo trong ~30–40 giây).

---

## Timeline chi tiết (`0:00` → `2:45`)

### `0:00 – 0:25` (25s) — Giới thiệu & Service Boundary

- **Thao tác màn hình:** Mở Slide 1–2 trong [`architecture_presentation.html`](../06_Plugathon/slides/architecture_presentation.html) hoặc ảnh [`service_boundary.png`](../06_Plugathon/diagrams/service_boundary.png).
- **Lời thoại gợi ý:**
  > "Xin chào thầy/cô và các bạn. Em là **Nguyễn Minh Phượng**, mã số sinh viên `<MãSinhViên>`, đại diện **Nhóm 6** phụ trách **Notification Service** trong hệ thống Smart Campus Operations Platform.
  > Như trên sơ đồ Service Boundary, Notification Service đóng vai **Consumer trong Pair 04** nhận cảnh báo từ **Core Business Service** qua MQTT topic `campus.alerts` và REST fallback `/notifications`, thực hiện validate, chống trùng, định tuyến đa kênh và lưu log vào PostgreSQL — hoàn toàn tách biệt khỏi IoT/AI hay luật nghiệp vụ sinh cảnh báo."

---

### `0:25 – 0:50` (25s) — Frozen Contract `v1.0.0` & Kiến trúc Triển khai

- **Thao tác màn hình:** Chuyển sang [`deployment_diagram.png`](../06_Plugathon/diagrams/deployment_diagram.png), sau đó chuyển sang Terminal gõ nhanh bước xác minh hợp đồng:
  ```powershell
  python 06_Plugathon/scripts/verify_frozen_contracts.py
  ```
- **Lời thoại gợi ý:**
  > "Hợp đồng Pair 04 gồm OpenAPI 3.1 (`v1.0.0`) và 4 JSON Schema Draft 2020-12 đã được khóa cứng tại `06_Plugathon/contracts/` và kiểm chứng parity SHA-256 `9/9` tệp khớp tuyệt đối.
  > Về triển khai, ngoài chế độ standalone 3 container (`api` non-root `uid=10001`, PostgreSQL 15 và Mosquitto 2), nhóm có sẵn overlay `docker-compose.external-broker.yml` để ghép trực tiếp vào mạng `class-net` của lớp qua biến môi trường `MQTT_BROKER_URL` mà không hard-code IP hay secret."

---

### `0:50 – 1:30` (40s) — Chạy Demo Pack & Kiểm tra `/health`, `/ready`

- **Thao tác màn hình:** Tại Terminal ở thư mục gốc repo, chạy script Demo Pack (không dùng `-Clean` lúc quay để còn mở Swagger UI ở bước sau):
  ```powershell
  # Windows PowerShell:
  .\demo\run_demo.ps1

  # (Hoặc trên Linux/macOS/Git Bash: ./demo/run_demo.sh)
  ```
  Trong khi script chạy đến bước `/health` và `/ready`, chuyển nhanh sang trình duyệt mở `http://127.0.0.1:8000/ready` và `http://127.0.0.1:8000/docs`.
- **Lời thoại gợi ý:**
  > "Bây giờ em chạy kịch bản tái lập tự động `run_demo`. Script tự sao chép `.env.example` thành `.env` tạm, lint OpenAPI bằng Spectral, kiểm tra Compose config và khởi động stack 3 container ở trạng thái healthy với user non-root `appuser`.
  > Trên trình duyệt, `GET /ready` xác nhận cả PostgreSQL và MQTT Mosquitto đều kết nối sẵn sàng, đồng thời Swagger UI hiển thị đầy đủ 7 endpoint theo OpenAPI 3.1."

---

### `1:30 – 2:15` (45s) — Live Pair-04 Handshake, Fault Injection & Retry Recovery

- **Thao tác màn hình:** Quay lại Terminal khi `run_plugathon_e2e.py --with-compose-dlq-recovery` đang in từng dòng `[PASS]`:
  - Chỉ vào các dòng log:
    1. `mqtt_alert_created_high_routing` (`severity=high` tự định tuyến gồm `discord`)
    2. `mqtt_q05_duplicate_idempotency` (chống trùng `event_id`)
    3. `fault_schema_invalid_dlq` (`SCHEMA_VALIDATION_FAILED` trên `campus.alerts.dlq`)
    4. `fault_q09_out_of_order_suppressed` (`SUPPRESSED_OUT_OF_ORDER`)
    5. `rest_duplicate_event_409` / `rest_invalid_token_401` / `rest_invalid_channel_422`
    6. `fault_max_retries_dlq_and_manual_retry_recovery` (`MAX_RETRIES_EXCEEDED` → `POST /notifications/{id}/retry` → `delivered`)
- **Lời thoại gợi ý:**
  > "Ở bước kiểm thử End-to-End Pair 04, script đóng vai Core Business bắn các sự kiện `alert.created`, `alert.escalated` và `alert.resolved` lên `campus.alerts`: mức `high` tự động định tuyến sang `telegram`, `email` và `discord`; trùng `event_id` (`Q05`) bị bỏ qua an toàn.
  > Với kịch bản lỗi: payload sai schema được chuyển thẳng sang topic `campus.alerts.dlq` với lý do `SCHEMA_VALIDATION_FAILED`; sự kiện trễ `Q09` bị chặn bằng cờ `SUPPRESSED_OUT_OF_ORDER`; và khi tiêm lỗi kênh `sms`, thông báo lỗi đẩy sang DLQ `MAX_RETRIES_EXCEEDED` rồi phục hồi thành công sang trạng thái `delivered` qua `POST /notifications/{id}/retry`."

---

### `2:15 – 2:45` (30s) — Newman Report, Dọn dẹp & Kết luận

- **Thao tác màn hình:**
  1. Mở [`06_Plugathon/reports/newman-plugathon.html`](../06_Plugathon/reports/newman-plugathon.html) trên trình duyệt để show kết quả `21` requests pass toàn bộ.
  2. Quay lại Terminal chạy lệnh dọn sạch stack (chứng minh không để lại `.env` hay container rác):
     ```powershell
     docker compose -f 06_Plugathon/docker-compose.yml down -v
     git status -s
     ```
- **Lời thoại gợi ý:**
  > "Cuối cùng, bộ kiểm thử Newman chạy đủ 21 request kiểm tra cả happy path, xác thực Bearer `401`, validation `422`, boundary `limit=101` trả `400`, idempotency `409` và thứ tự `Q09`, xuất báo cáo HTML đầy đủ.
  > Toàn bộ log, ảnh chụp màn hình, biên bản lỗi và nhận xét hạn chế trung thực đều được lưu tại `06_Plugathon/evidence/` và `06_Plugathon/known-issues.md`. Sau khi chạy `docker compose down -v`, môi trường sạch hoàn toàn và không rò rỉ `.env` hay secret nào. Em xin cảm ơn thầy/cô đã theo dõi!"

---

## Lưu ý sau khi quay xong

- Xuất video `.mp4` hoặc upload lên Google Drive / YouTube Unlisted.
- Dán link thật vào dòng `VIDEO_URL=` trong [`06_Plugathon/evidence/demo_video_link.txt`](../06_Plugathon/evidence/demo_video_link.txt).
