# Docker Evidence – Lab 04 (Notification Service)

## Team

- **Team:** Nhóm 6
- **Service:** `notification-service` (Pair 04: `Core Business → Notification`)
- **Image tag:** `fit4110/notification-service:lab04` (`ID: 27df7fcc95f3`, kích thước `276MB`)

---

## 1. Unit Tests & Build evidence

```bash
docker build --target test -t fit4110/notification-service:test .
docker build -t fit4110/notification-service:lab04 .
```

- Kết quả stage `test`: **`13 passed`, `1 warning` in `0.51s`** ([`docker-test-stage.log`](./docker-test-stage.log)).
- Kết quả stage `runtime`: Build thành công multi-stage image `fit4110/notification-service:lab04` (`ID: 27df7fcc95f3`, `276MB`) ([`docker-build.log`](./docker-build.log), [`docker-images.txt`](./docker-images.txt)).

---

## 2. Run & Non-root / Healthcheck evidence

```bash
docker run -d --rm \
  --name fit4110-notify-lab04 \
  -p 8000:8000 \
  --env-file .env.example \
  fit4110/notification-service:lab04
```

- Health state (`docker inspect`): `healthy` ([`docker-run-health.log`](./docker-run-health.log)).
- User bên trong container (`docker exec fit4110-notify-lab04 id`):
  `uid=10001(appuser) gid=10001(appgroup) groups=10001(appgroup)`.
- Container runtime logs: [`docker-container.log`](./docker-container.log).

---

## 3. HTTP `GET /health` evidence

```bash
curl -s -i http://localhost:8000/health
```

Kết quả thực tế ([`curl-health.txt`](./curl-health.txt)):

```http
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok","service":"notification-service","mqtt_broker":"mqtt://192.168.1.51:1883","subscribed_topic":"campus.alerts","time":"2026-11-13T10:55:06Z"}
```

---

## 4. Newman Verification evidence

```bash
npm run test:local
```

Kết quả ([`newman-local-cli.txt`](./newman-local-cli.txt)):

- **Executed:** `18 requests`, `33 assertions`
- **Failed:** **`0 failed`**
- **Total run duration / Average response time:** `1621ms` / **`6ms`** (`min: 2ms, max: 26ms, s.d.: 5ms`)
- **Reports (Local Docker):** [`../../reports/newman-lab04-local.html`](../../reports/newman-lab04-local.html), [`../../reports/newman-lab04-local.xml`](../../reports/newman-lab04-local.xml)
- **Prism Mock (`npm run test:mock`):** **18 requests, 33 assertions, 0 failed** (`1757ms`, avg **`14ms`**, `min: 5ms, max: 41ms`, mock skip `TC11`/`TC18`) — [`../../reports/newman-lab04-mock.html`](../../reports/newman-lab04-mock.html), [`../../reports/newman-lab04-mock.xml`](../../reports/newman-lab04-mock.xml)
