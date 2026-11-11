# 03_Postman — Kiểm thử Hợp đồng Queue Async (Ajv) & REST Mock/Newman (Nhóm 6: Notification Service)

**Học phần:** FIT4110 – Dịch vụ kết nối và Công nghệ nền tảng  
**Buổi 03:** Kiểm thử Hợp đồng Event Queue Async (`Lab03_Kiểm thử Queue-Async.pdf`) & Kiểm thử tích hợp Postman + Newman (`FIT4110_lab03_postman_mock_testing`)  
**Đề tài:** Nhóm 6 — Notification Service (Cặp #4: `Core Business → Notification Service`)

---

## 1. Tổng quan kiến trúc kiểm thử Buổi 03

Theo đúng nguyên tắc của Buổi 03:
1. **Nhánh chính — Queue Async (`queue-contract-tests/pair-04-core-notification/`):**
   - Kiểm thử hợp đồng sự kiện bất đồng bộ từ **Core Business (Producer)** sang **Notification Service (Consumer)** trên topic `campus.alerts` (MQTT Broker `mqtt://192.168.1.51:1883`, DLQ `campus.alerts.dlq`).
   - Sử dụng **JSON Schema Draft 2020-12** + **Ajv (`ajv`, `ajv-formats`)** để kiểm tra tự động:
     - **Mức A (Schema Validation):** 06 mẫu hợp lệ (`alert.created`, `alert.escalated`, `alert.resolved` + boundary) đều `PASS`; 08 mẫu không hợp lệ có chủ đích (`Q02`, `Q03`, `Q04`) đều bị từ chối (`PASS expected-invalid`).
     - **Mức B (Semantic Stub `Q05–Q09`):** Kiểm tra tự động logic Idempotency/Dedupe theo `event_id` (`Q05`), Retry tối đa 3 lần × 5s (`Q06`), chuyển `campus.alerts.dlq` khi quá 3 lần retry (`Q07`), từ chối `event_name` lạ (`Q08`), và chặn cảnh báo giả khi sự kiện đến trễ / out-of-order (`Q09`).
   - **Không tạo REST endpoint giả cho Queue.**
2. **Nhánh bổ trợ — REST Fallback & Consumer Smoke (`postman/`, `contracts/`, `reports/`):**
   - Kiểm thử các endpoint REST quản trị & dự phòng của Notification Service (`GET /health`, `POST /notifications`, `GET /notifications`, `GET /notifications/recent`, `GET /notifications/{id}`, `POST /notifications/{id}/retry`) và **Consumer-side Smoke Test (`TC15`)** gọi sang Mock Server của `core-business.openapi.yaml` (`GET /alerts/{alertId}`) bằng **Prism + Postman + Newman**.

---

## 2. Cấu trúc thư mục `03_Postman/`

```text
03_Postman/
├── README.md
├── CONTRIBUTION.md
├── package.json
├── .spectral.yaml
├── queue-contract-tests/                                 # [NHÁNH CHÍNH] Kiểm thử Queue Async (Pair 04)
│   ├── README.md
│   └── pair-04-core-notification/
│       ├── event-contract.md                             # Hợp đồng Event chuẩn v1.0 đã chốt với Core Business
│       ├── package.json                                  # Khai báo ajv & ajv-formats
│       ├── schema/
│       │   ├── alert.created.schema.json                 # Schema canonical cho alert.created
│       │   ├── alert.escalated.schema.json               # Schema canonical cho alert.escalated
│       │   ├── alert.resolved.schema.json                # Schema canonical cho alert.resolved
│       │   └── campus.alerts.schema.json                 # Schema tổng hợp oneOf cho topic campus.alerts
│       ├── samples/
│       │   ├── valid/                                    # 06 mẫu hợp lệ (2 mẫu/event)
│       │   └── invalid/                                  # 08 mẫu lỗi có chủ đích (Q02, Q03, Q04)
│       ├── scripts/
│       │   └── test-event-contract.js                    # Script kiểm tra tự động Ajv + Semantic Stub Q05-Q09
│       ├── event-test-matrix.md                          # Ma trận kiểm thử Q01–Q09 và đặc thù Pair 04
│       ├── producer-consumer-handshake.md                # Biên bản xác nhận READY giữa Core & Notification
│       └── reports/
│           └── event-contract-test.txt                   # Bằng chứng kết quả chạy test Queue Async
├── contracts/                                            # [NHÁNH BỔ TRỢ] OpenAPI 3.1.0 Contracts
│   ├── notification.openapi.yaml                         # Hợp đồng REST của Notification Service (Port 4010)
│   └── core-business.openapi.yaml                        # Hợp đồng REST của Core Business (Port 4011)
├── postman/
│   ├── collections/
│   │   ├── FIT4110_lab03_notification.postman_collection.json
│   │   └── team-notify.postman_collection.json
│   └── environments/
│       ├── FIT4110_lab03_mock.postman_environment.json
│       ├── FIT4110_lab03_local.postman_environment.json
│       ├── team-notify_mock.postman_environment.json
│       └── team-notify_local.postman_environment.json
├── mock-data/
│   ├── notification-valid.json
│   ├── notification-invalid-channel.json
│   └── notification-boundary.json
├── checklists/
│   ├── reliability_checklist.md
│   └── submission_checklist.md
├── templates/
│   ├── test-case-matrix.csv
│   └── consumer-provider-handshake.md
├── reports/
│   ├── contract-lint-report.txt
│   ├── newman-report.xml
│   └── newman-report.html
└── .github/
    └── workflows/
        └── newman.yml
```

---

## 3. Hướng dẫn chạy kiểm thử

### 3.1. Chạy bộ kiểm thử Queue Async (Pair 04)
```powershell
cd .\queue-contract-tests\pair-04-core-notification
npm install
node .\scripts\test-event-contract.js 2>&1 | Tee-Object -FilePath .\reports\event-contract-test.txt
```

### 3.2. Chạy Spectral Lint + Prism Mock + Newman
```powershell
cd ..\. # Quay về thư mục 03_Postman
npm install
npm run lint:contracts
# Khởi chạy Prism Mock cho Notification (4010) và Core Business (4011), sau đó chạy:
npm run test:mock
npm run test:html
```
