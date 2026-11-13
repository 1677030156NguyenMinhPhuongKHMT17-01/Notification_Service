# FIT 4110 SET-UP MÔI TRƯỜNG

Buổi 1 tập trung vào việc đưa máy cá nhân của sinh viên về trạng thái sẵn sàng để học các buổi tiếp theo:

- Cài và kiểm tra Git, Docker, Docker Compose, Node.js, Python hoặc Miniconda.
- Chạy được container Docker cơ bản.
- Tải trước các Docker image dùng trong học phần.
- Chạy được smoke test môi trường lab.
- Tạo và nộp minh chứng học tập trong thư mục `evidence/buoi-01/`.

> Lưu ý: Trong quy trình **FIT4110 Student Kit** (một repository portfolio duy nhất `FIT4110_<MãSinhViên>` cho cả học kỳ), toàn bộ nội dung Buổi 1 nằm trong thư mục `01_Setup/`. Sinh viên di chuyển vào thư mục `01_Setup/` trước khi chạy các script `./scripts/*` hoặc `.\scripts\*`.

---

## 1. Hướng dẫn sử dụng

Quy trình thực hiện Buổi 1 gồm 5 bước:

```text
Bước 1. Tạo hoặc clone repository portfolio duy nhất FIT4110_<MãSinhViên> về máy.
Bước 2. Đặt starter Buổi 1 (không kèm .git) vào thư mục 01_Setup/ và mở terminal tại 01_Setup/.
Bước 3. Chạy script tải image (pull_all), smoke test và thu thập minh chứng (collect_session01_evidence).
Bước 4. Hoàn thiện service-boundary.md, checklist.md, known-issues.md và kiểm tra bằng verify_submission.py.
Bước 5. Commit + push thư mục 01_Setup/evidence/buoi-01/ lên GitHub repository portfolio.
```

---

## 2. Chuẩn bị Repository Portfolio (`FIT4110_<MãSinhViên>`)

### 2.1. Quy ước đặt tên và cấu trúc

Theo `FIT4110_Student_Kit/03_Guides/Submission.md`, mỗi sinh viên dùng **một repository GitHub public duy nhất** cho toàn bộ học kỳ theo mẫu:

```text
FIT4110_<MãSinhViên>
```

Mỗi buổi học nằm trong một thư mục top-level tương ứng (`01_Setup/`, `02_OpenAPI/`, `03_Postman/`, `04_Docker/`, `05_Compose/`, `06_Plugathon/`).

### 2.2. Ghi chú lịch sử starter (`FIT4110_setup`)

Starter gốc ban đầu được thiết kế cho repo đơn lẻ (`s01-environment-setup-<github-username>`). Khi tích hợp vào portfolio `FIT4110_<MãSinhViên>`, sinh viên giữ nguyên cấu trúc bên trong `01_Setup/` và ghi nhận lịch sử commit của chính portfolio repo vào `evidence/buoi-01/git-log.txt`.

---

## 3. Clone repository portfolio về máy

Mở Terminal, Git Bash hoặc PowerShell:

```bash
git clone <URL_REPO_PORTFOLIO_FIT4110_MSSV>
cd FIT4110_<MãSinhViên>/01_Setup
```

Ví dụ:

```bash
git clone https://github.com/<account>/FIT4110_<MãSinhViên>.git
cd FIT4110_<MãSinhViên>/01_Setup
```

---

## 4. Chạy bài trên macOS hoặc Linux

### 4.1. Cấp quyền chạy script

```bash
chmod +x scripts/*.sh
```

### 4.2. Tải trước Docker image

```bash
./scripts/pull_all.sh
```

Script này sẽ tải các image cần dùng trong học phần, ví dụ:

```text
registry:2
python:3.11-slim
node:20-alpine
postgres:15-alpine
rabbitmq:3-management
eclipse-mosquitto:2
nginx:alpine
traefik:v3.1
prom/prometheus:v2.54.1
grafana/grafana:11.2.0
redis:7-alpine
swaggerapi/swagger-ui:v5.17.14
hello-world:latest
ultralytics/ultralytics:latest-cpu
```

### 4.3. Chạy smoke test

```bash
./scripts/smoke_test.sh
```

### 4.4. Sinh minh chứng Buổi 1

```bash
./scripts/collect_session01_evidence.sh
```

Sau bước này, kiểm tra thư mục và chạy script xác minh cấu trúc nộp bài:

```bash
ls evidence/buoi-01
python3 ./scripts/verify_submission.py
```

---

## 5. Chạy bài trên Windows PowerShell

Mở PowerShell tại thư mục repo bài làm của em.

### 5.1. Cho phép chạy script trong phiên hiện tại

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 5.2. Tải trước Docker image

```powershell
.\scripts\pull_all.ps1
```

### 5.3. Chạy smoke test

```powershell
.\scripts\smoke_test.ps1
```

### 5.4. Sinh minh chứng Buổi 1

```powershell
.\scripts\collect_session01_evidence.ps1
```

Sau bước này, kiểm tra thư mục và chạy script xác minh (có thể chạy từ `01_Setup/` hoặc từ thư mục gốc portfolio `python 01_Setup/scripts/verify_submission.py`):

```powershell
Get-ChildItem evidence\buoi-01
python .\scripts\verify_submission.py
```

---

## 6. Nếu dùng Miniconda

Nếu máy dùng Miniconda, hãy tạo môi trường riêng cho học phần:

```bash
conda env create -f environment.yml
conda activate api-platform
python --version
```

Nếu môi trường đã tồn tại, có thể dùng:

```bash
conda activate api-platform
pip install -r requirements.txt
```

Yêu cầu khuyến nghị:

```text
Python 3.11.x
pip 24.x hoặc mới hơn
```

---

## 7. Minh chứng cần nộp

Sau khi chạy script, thư mục `evidence/buoi-01/` cần có các file sau:

```text
evidence/buoi-01/
  README.md
  checklist.md
  known-issues.md
  tool-versions.txt
  docker-version.txt
  compose-version.txt
  hello-world.txt
  smoke-test-result.txt
  image-list.txt
  git-log.txt
  service-boundary.md
```

Ý nghĩa của từng file:

| File | Ý nghĩa |
|---|---|
| `tool-versions.txt` | Phiên bản Git, Docker, Node, Python trên máy em |
| `docker-version.txt` | Thông tin Docker CLI/Engine |
| `compose-version.txt` | Thông tin Docker Compose |
| `hello-world.txt` | Minh chứng Docker chạy được container cơ bản |
| `smoke-test-result.txt` | Kết quả kiểm tra môi trường lab |
| `image-list.txt` | Danh sách Docker image đã có trên máy |
| `git-log.txt` | Lịch sử commit gần nhất |
| `checklist.md` | Checklist tự xác nhận của sinh viên |
| `known-issues.md` | Lỗi còn tồn tại, nếu có |
| `service-boundary.md` | Mô tả Actor, Boundary, Service, Input/Output, API dự kiến và phụ thuộc với service khác của nhóm |

---

## 8. Nộp bài bằng commit và push

Sau khi có minh chứng, chạy từ thư mục gốc repository `FIT4110_<MãSinhViên>`:

```bash
git status
git add 01_Setup/evidence/buoi-01 01_Setup/CONTRIBUTION.md
git commit -m "Add session 01 environment evidence"
git push
```

Nếu Git báo chưa cấu hình tên/email:

```bash
git config --global user.name "Ho Ten Sinh Vien"
git config --global user.email "email-cua-em@example.com"
```

Sau khi push, mở repo portfolio trên GitHub và kiểm tra xem thư mục `01_Setup/evidence/buoi-01/` đã xuất hiện chưa.

---

## 9. Có cần tạo branch không?

Với Buổi 1 trong portfolio `FIT4110_<MãSinhViên>`, thông thường sinh viên có thể commit trực tiếp lên nhánh mặc định (`main`) của repo portfolio.

Không cần tạo branch riêng, trừ khi giảng viên yêu cầu.

Nếu giảng viên yêu cầu tạo branch, dùng mẫu:

```bash
git checkout -b feat/s1-setup-<MãSinhViên>
```

Ví dụ:

```bash
git checkout -b feat/s1-setup-21123456
```

---

## 10. Quy định không được commit

Không commit các loại file sau:

```text
*.doc
*.docx
*.ppt
*.pptx
*.pdf dung lượng lớn
.env chứa mật khẩu thật
file model lớn hơn 100 MB
file dữ liệu lớn không được yêu cầu
```

Thư mục `01_Setup/.github/workflows/` lưu giữ workflow kiểm tra tham chiếu từ starter gốc; đối với repository portfolio một repo duy nhất (`FIT4110_<MãSinhViên>`), GitHub Actions thực tế chạy từ thư mục gốc `.github/workflows/`. Tuyệt đối không commit file Word `.doc`/`.docx`.

---

## 11. Tiêu chí hoàn thành Buổi 1

Sinh viên được xem là hoàn thành Buổi 1 khi:

- Repository portfolio `FIT4110_<MãSinhViên>` có đầy đủ thư mục `01_Setup/`.
- `docker run --rm hello-world` chạy thành công.
- `docker compose version` chạy thành công.
- `scripts/smoke_test` đã chạy và sinh log.
- Thư mục `01_Setup/evidence/buoi-01/` có đầy đủ 11 file minh chứng và `python scripts/verify_submission.py` báo `PASS`.
- Đã hoàn thiện `01_Setup/CONTRIBUTION.md` và commit/push minh chứng lên repo portfolio.
- Nếu còn lỗi hoặc sai lệch lịch sử snapshot, đã ghi rõ vào `01_Setup/evidence/buoi-01/known-issues.md`.
- Đã nộp `01_Setup/evidence/buoi-01/service-boundary.md` mô tả Service Boundary của nhóm.

---

## 12. Xử lý lỗi nhanh

### Docker chưa chạy

Mở Docker Desktop và chờ biểu tượng Docker chuyển sang trạng thái running, sau đó chạy lại:

```bash
docker info
```

### Thiếu image

Chạy lại:

```bash
./scripts/pull_all.sh
```

Windows:

```powershell
.\scripts\pull_all.ps1
```

### Lỗi Ultralytics trên Mac Apple Silicon

Nếu thấy cảnh báo khác nền tảng `linux/amd64` và `linux/arm64/v8`, có thể chạy thử:

```bash
docker run --rm --platform linux/amd64 ultralytics/ultralytics:latest-cpu yolo version
```

### Port 5000 hoặc 8081 bị chiếm

Dừng container đang chạy:

```bash
docker ps
docker stop <container_id>
```

Hoặc xem thêm hướng dẫn trong:

```text
docs/troubleshooting.md
```

---

## 13. Câu chốt của Buổi 1

> Không nộp “em đã cài xong”, mà nộp **minh chứng có thể kiểm tra lại được**.
