# Chính sách Quản lý Phiên bản Hợp đồng (API & Event Versioning Policy)

- **Service:** Notification Service (Nhóm 6)
- **Cặp phụ thuộc:** Pair #4 — Core Business → Notification Service
- **Phiên bản hiện tại:** `1.0.0`
- **Áp dụng cho:**
  1. Hợp đồng OpenAPI 3.1 (`openapi.yaml`)
  2. Hợp đồng sự kiện bất đồng bộ (`event-contract-04-core-notification.md` trên topic `campus.alerts`)

---

## 1. Quy tắc đánh số phiên bản (Semantic Versioning — `MAJOR.MINOR.PATCH`)

Nhóm áp dụng chuẩn **Semantic Versioning 2.0.0 (`MAJOR.MINOR.PATCH`)** cho cả REST API và Event Contract:

| Thành phần | Khi nào tăng? | Ví dụ |
|---|---|---|
| **MAJOR (`X.0.0`)** | Khi có **Breaking Change** (thay đổi không tương thích ngược) làm ảnh hưởng tới Consumer/Producer hiện tại. | Đổi tên trường `alert_id` thành `id`, xóa trường `severity`, đổi cấu trúc topic `campus.alerts`. |
| **MINOR (`1.X.0`)** | Khi thêm tính năng/trường mới nhưng **Backward-Compatible** (tương thích ngược hoàn toàn). | Thêm kênh mới vào enum `NotificationChannel`, thêm trường tùy chọn `metadata` vào payload `alert.created`, hoặc thêm endpoint `GET /notifications/stats`. |
| **PATCH (`1.0.X`)** | Khi sửa lỗi chính tả, bổ sung mô tả `description`, thêm `examples` mà không làm thay đổi schema hay hành vi hợp đồng. | Bổ sung ví dụ JSON hoặc làm rõ mô tả lỗi trong `openapi.yaml`. |

---

## 2. Phân loại thay đổi Tương thích ngược vs Phá vỡ hợp đồng

### 2.1. Thay đổi tương thích ngược (Backward-Compatible Changes — An toàn)
- Thêm một endpoint REST mới (ví dụ: `POST /notifications/{notification_id}/retry`).
- Thêm một trường **không bắt buộc (optional)** vào Request Body hoặc Event Payload trên topic `campus.alerts`.
- Thêm một trường mới vào Response Body của `NotificationLog` (Consumer áp dụng nguyên tắc *Tolerant Reader* — bỏ qua các trường lạ chưa biết).
- Thêm một loại sự kiện mới trên hệ thống mà không sửa đổi cấu trúc của `alert.created`, `alert.escalated`, `alert.resolved`.

### 2.2. Thay đổi phá vỡ hợp đồng (Breaking Changes — Phải đàm phán & tăng MAJOR)
- Đổi tên trường đã chốt trong `event-contract-04-core-notification.md` (ví dụ: đổi `event_id` thành `eventId` hoặc đổi `correlationId` thành `correlation_id`).
- Chuyển một trường từ tùy chọn (`target_channels`) sang bắt buộc (`required`).
- Thu hẹp tập giá trị enum của `severity` (`low`, `medium`, `high`, `critical`) hoặc thay đổi kiểu dữ liệu của `escalation_level` từ `integer` sang `string`.
- Thay đổi mã HTTP status code thành công hoặc thay đổi cấu trúc lỗi `Problem Details (RFC 9457)`.

---

## 3. Quy trình Deprecation & `Sunset` Header

Khi cần loại bỏ một endpoint hoặc một trường dữ liệu cũ:

1. **Thông báo trước & Đàm phán:** Báo trước cho nhóm đối tác (`Core Business` / `Analytics`), cập nhật `negotiation-log.md` và `changelog.md`.
2. **Đánh dấu `deprecated: true` trong `openapi.yaml`:**
   ```yaml
   parameters:
     - name: legacy_channel
       in: query
       deprecated: true
       description: "ĐÃ NGỪNG KHUYẾN NGHỊ: Hãy dùng tham số 'channel' thay thế. Sẽ gỡ bỏ sau ngày Sunset."
       schema:
         type: string
   ```
3. **Trả về HTTP Header `Deprecation` và `Sunset` (theo RFC 8594):**
   Khi Consumer gọi vào endpoint sắp ngừng hỗ trợ, Notification Service trả kèm header:
   ```http
   Deprecation: true
   Sunset: Wed, 30 Dec 2026 23:59:59 GMT
   Link: <https://api.campus.local/docs/migration-v2>; rel="sunset"
   ```
4. **Hỗ trợ song song (Grace Period):** Trong thời gian trước thời điểm `Sunset`, Notification Service vẫn chấp nhận cả định dạng cũ và định dạng mới trước khi chính thức cắt bỏ ở phiên bản `2.0.0`.

