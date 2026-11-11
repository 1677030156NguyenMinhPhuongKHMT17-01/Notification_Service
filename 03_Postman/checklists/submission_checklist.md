# Submission Checklist — Lab 03 (Nhóm 6: Notification Service)

Trước khi nộp, thư mục `03_Postman/` đã có đầy đủ cả **2 nhánh kiểm thử** (Queue Async theo `Lab03_Kiểm thử Queue-Async.pdf` và REST/Newman theo `FIT4110_lab03_postman_mock_testing`):

## 1. Nhánh Queue Async (`queue-contract-tests/pair-04-core-notification/`)

- [x] `queue-contract-tests/README.md`
- [x] `queue-contract-tests/pair-04-core-notification/event-contract.md`
- [x] `queue-contract-tests/pair-04-core-notification/schema/alert.created.schema.json`
- [x] `queue-contract-tests/pair-04-core-notification/schema/alert.escalated.schema.json`
- [x] `queue-contract-tests/pair-04-core-notification/schema/alert.resolved.schema.json`
- [x] `queue-contract-tests/pair-04-core-notification/schema/campus.alerts.schema.json`
- [x] `queue-contract-tests/pair-04-core-notification/samples/valid/` (06 valid samples)
- [x] `queue-contract-tests/pair-04-core-notification/samples/invalid/` (08 invalid samples)
- [x] `queue-contract-tests/pair-04-core-notification/scripts/test-event-contract.js`
- [x] `queue-contract-tests/pair-04-core-notification/event-test-matrix.md` (`Q01–Q09`)
- [x] `queue-contract-tests/pair-04-core-notification/producer-consumer-handshake.md` (`READY`)
- [x] `queue-contract-tests/pair-04-core-notification/reports/event-contract-test.txt`

## 2. Nhánh REST Fallback & Consumer Smoke (`03_Postman/` root)

- [x] `contracts/notification.openapi.yaml` & `contracts/core-business.openapi.yaml`
- [x] `postman/collections/FIT4110_lab03_notification.postman_collection.json` (và bản sao `team-notify.postman_collection.json`)
- [x] `postman/environments/FIT4110_lab03_mock.postman_environment.json` (và `team-notify_mock.postman_environment.json`)
- [x] `postman/environments/FIT4110_lab03_local.postman_environment.json` (và `team-notify_local.postman_environment.json`)
- [x] `reports/contract-lint-report.txt`
- [x] `reports/newman-report.xml` & `reports/newman-report.html`
- [x] `checklists/reliability_checklist.md`
- [x] `templates/test-case-matrix.csv`
- [x] `templates/consumer-provider-handshake.md`
- [x] `CONTRIBUTION.md`
