# Queue Async Contract Testing — Lab 03

Thư mục này chứa bộ kiểm thử hợp đồng **Queue Async (Event Contract Testing)** cho **Nhóm 6 — Notification Service** theo đúng hướng dẫn trong tài liệu `Lab03_Kiểm thử Queue-Async.pdf`.

## Cặp phụ thuộc được kiểm thử

- **Pair 04:** `Core Business (Producer) → Notification Service (Consumer)`
- **Topic / Broker:** `campus.alerts` trên MQTT Broker `mqtt://192.168.1.51:1883` (DLQ: `campus.alerts.dlq`)
- **Các Event trọng tâm:** `alert.created`, `alert.escalated`, `alert.resolved`

## Cấu trúc thư mục

```text
queue-contract-tests/
├── README.md
└── pair-04-core-notification/
    ├── event-contract.md                 # Hợp đồng Event đã chốt từ Lab 02
    ├── package.json                      # Khai báo ajv & ajv-formats
    ├── schema/
    │   ├── alert.created.schema.json     # Schema canonical cho alert.created
    │   ├── alert.escalated.schema.json   # Schema canonical cho alert.escalated
    │   ├── alert.resolved.schema.json    # Schema canonical cho alert.resolved
    │   └── campus.alerts.schema.json     # Schema tổng hợp (oneOf 3 event trên topic campus.alerts)
    ├── samples/
    │   ├── valid/                        # 06 mẫu hợp lệ (02 mẫu/event: happy path + boundary)
    │   └── invalid/                      # 08 mẫu không hợp lệ có chủ đích (Q02, Q03, Q04)
    ├── scripts/
    │   └── test-event-contract.js        # Script kiểm tra tự động bằng Ajv Draft 2020-12
    ├── event-test-matrix.md              # Ma trận kiểm thử Q01–Q09 và điểm đặc thù Pair 04
    ├── producer-consumer-handshake.md    # Biên bản xác nhận READY giữa Core Business & Notification
    └── reports/
        └── event-contract-test.txt       # Bằng chứng kết quả chạy script tự động
```

## Cách chạy kiểm thử tự động trên Windows PowerShell

```powershell
cd .\queue-contract-tests\pair-04-core-notification
npm install
node .\scripts\test-event-contract.js 2>&1 | Tee-Object -FilePath .\reports\event-contract-test.txt
```

