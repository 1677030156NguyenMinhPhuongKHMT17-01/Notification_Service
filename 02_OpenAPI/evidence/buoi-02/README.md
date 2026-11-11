# Evidence Buổi 02 — Notification Service (Nhóm 6)

Thư mục này lưu toàn bộ bằng chứng hoàn thành **Lab 02 (Contract-First: Event Contract #4 & OpenAPI 3.1)** của **Notification Service (Nhóm 6)**.

## Danh mục file minh chứng trong `evidence/buoi-02/`

```text
evidence/buoi-02/
  README.md
  checklist.md
  known-issues.md
  spectral-report.txt
  tool-versions.txt
  git-log.txt
  curl-mock-test-output.txt
  mock-screenshots/
    req-01-health-200.png
    req-02-recent-notifications-200.png
    req-03-send-notification-201.png
    req-04-unauthorized-401.png
    req-05-invalid-payload-422.png
```

## Cách sinh report Spectral & Evidence

macOS/Linux:

```bash
./scripts/collect_session02_evidence.sh
```

Windows PowerShell:

```powershell
.\scripts\collect_session02_evidence.ps1
```

## Kiểm thử Prism Mock Server bằng `curl` (5 Requests: 3 Happy Path + 2 Error Case)

Khởi động Prism mock server ở cổng `4010`:

```powershell
prism mock openapi.yaml --port 4010
```

Chạy script kiểm thử 5 request `curl` tới `http://localhost:4010`:

```powershell
.\scripts\test_mock_with_curl.ps1
```

5 kịch bản kiểm thử được chụp ảnh trong `mock-screenshots/`:
1. **`req-01-health-200.png`:** Happy path `GET /health` → `200 OK` (trả về trạng thái kết nối MQTT `mqtt://192.168.1.51:1883` và topic `campus.alerts`).
2. **`req-02-recent-notifications-200.png`:** Happy path `GET /notifications/recent` (có Bearer token) → `200 OK` (trả về danh sách thông báo phân trang cursor).
3. **`req-03-send-notification-201.png`:** Happy path `POST /notifications` với JSON mẫu `alert.created` (`snake_case` của Core Business) → `201 Created`.
4. **`req-04-unauthorized-401.png`:** Error case `GET /notifications/recent` không truyền Bearer token → `401 Unauthorized` (`application/problem+json`).
5. **`req-05-invalid-payload-422.png`:** Error case `POST /notifications` gửi payload sai định dạng schema → `422 Unprocessable Entity` / `400 Bad Request` (`application/problem+json`).
