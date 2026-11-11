# Minh chứng Buổi 1 — Thiết lập môi trường & Service Boundary

Thư mục này lưu trữ toàn bộ minh chứng thiết lập môi trường lab và tài liệu phân tích ranh giới dịch vụ (**Service Boundary**) của **Notification Service** ở Buổi 1.

## Sinh viên điền thông tin

- **Họ tên:** Nguyễn Minh Phượng _(cập nhật nếu cần)_
- **Mã sinh viên:** `<MãSinhViên>`
- **Lớp:** FIT4110 – Dịch vụ kết nối và Công nghệ nền tảng
- **Nhóm:** Nhóm A7 – Product A _(hoặc B7 – Product B)_
- **Service phụ trách:** Notification Service (Dịch vụ gửi cảnh báo đa kênh)
- **Vai trò dự kiến trong nhóm:** Service Lead / Backend & DevOps Owner _(cập nhật theo phân công nhóm)_
- **Hệ điều hành:** Windows 11 (PowerShell + Docker Desktop WSL2 backend)
- **Ghi chú:** Đã hoàn thành kiểm tra công cụ, tải bộ Docker image chuẩn, chạy smoke test thành công và đặc tả đầy đủ `service-boundary.md` cho Notification Service.

## Danh sách 11 file minh chứng bắt buộc trong `evidence/buoi-01/`

| File                    | Ý nghĩa                                                                                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `README.md`             | Thông tin sinh viên, nhóm và mô tả danh mục minh chứng Buổi 1                                                                |
| `checklist.md`          | Checklist tự kiểm tra công cụ, Docker, GitHub và OBE Evidence                                                                |
| `known-issues.md`       | Ghi nhận lỗi phát sinh (nếu có) và hướng xử lý trong quá trình setup                                                         |
| `tool-versions.txt`     | Phiên bản Git, Docker, Docker Compose, Node.js, npm, Python, pip trên máy                                                    |
| `docker-version.txt`    | Thông tin phiên bản Docker CLI / Engine                                                                                      |
| `compose-version.txt`   | Thông tin phiên bản Docker Compose v2                                                                                        |
| `hello-world.txt`       | Minh chứng chạy thành công container `hello-world`                                                                           |
| `image-list.txt`        | Danh sách các Docker image đã pull về máy                                                                                    |
| `smoke-test-result.txt` | Kết quả kiểm tra tự động môi trường lab (`[PASS]` / `[WARN]` / `[FAIL]`)                                                     |
| `git-log.txt`           | Lịch sử commit gần nhất của repository portfolio cá nhân                                                                     |
| `service-boundary.md`   | Đặc tả chi tiết Actor, System/Service Boundary, Input/Output, API, Upstream/Downstream và sơ đồ của **Notification Service** |

## Cách sinh file tự động

macOS/Linux:

```bash
./scripts/collect_session01_evidence.sh
```

Windows PowerShell:

```powershell
.\scripts\collect_session01_evidence.ps1
python .\scripts\verify_submission.py
```
