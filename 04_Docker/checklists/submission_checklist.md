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
- [x] Tên & tag image (`fit4110/notification-service:lab04` — ghi rõ trong `evidence/buoi-04/README.md` và `docker-images.txt`)
