# Submission Checklist – Lab 04 (Notification Service – Nhóm 6)

Nộp các minh chứng sau:

- [x] `Dockerfile`
- [x] `.dockerignore`
- [x] `.env.example`
- [x] `RUN_LOCAL.md`
- [x] Contract OpenAPI đã dùng (`contracts/notification.openapi.yaml`, `contracts/core-business.openapi.yaml`)
- [x] Postman Collection đã chạy trên container (`postman/collections/FIT4110_lab04_notification_docker.postman_collection.json`)
- [x] Postman Environment local/docker (`postman/environments/FIT4110_lab04_local.postman_environment.json`)
- [x] Newman report XML/HTML (`reports/newman-lab04-local.xml`, `reports/newman-lab04-local.html`)
- [x] Log `docker build` (`evidence/buoi-04/docker-build.log`, `evidence/buoi-04/docker-test-stage.log`)
- [x] Log `docker run` & `docker logs` (`evidence/buoi-04/docker-run-health.log`, `evidence/buoi-04/docker-container.log`)
- [x] Log `GET /health` (`evidence/buoi-04/curl-health.txt`)
- [x] Tên & tag image local (`fit4110/notification-service:lab04` — ghi rõ trong `evidence/buoi-04/README.md` và `docker-images.txt`)
- [x] Tài liệu đóng góp & lỗi tồn đọng (`CONTRIBUTION.md`, `known-issues.md`)

## Ghi chú trung thực về trạng thái nộp bài (Local vs Remote)

- **Git remote & GitHub Actions:** `git remote -v` hiện chưa được cấu hình và các thay đổi gần nhất còn đang ở workspace local; vì vậy workflow [`../../.github/workflows/lab04-docker-newman.yml`](../../.github/workflows/lab04-docker-newman.yml) mới chỉ kiểm chứng cấu hình ở local và sẽ chỉ chạy thực tế trên GitHub Actions sau khi commit & push lên remote repository.
- **Docker Registry:** Image `fit4110/notification-service:lab04` mới build và kiểm thử ở Docker local (chưa `docker push` lên Docker Hub / GHCR).
- **Minh chứng hình ảnh:** Thư mục `evidence/buoi-04/` hiện lưu đầy đủ CLI log và báo cáo Newman XML/HTML (chưa có ảnh chụp màn hình `.png`; xem chi tiết tại `known-issues.md`).
