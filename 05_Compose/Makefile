.PHONY: install lint test-unit build compose-up compose-down compose-ps logs readiness test-compose

IMAGE_NAME ?= fit4110/notification-service:v0.1.0-team-notify
APP_PORT ?= 8000

install:
	npm install

lint:
	npm run lint:openapi

test-unit:
	docker build --target test -t fit4110/notification-service:test .

build:
	docker build -t $(IMAGE_NAME) .

compose-up:
	docker compose up -d --build --wait

compose-down:
	docker compose down

compose-ps:
	docker compose ps

logs:
	docker compose logs -f

readiness:
	curl -fsS http://localhost:$(APP_PORT)/health
	@echo ""
	curl -fsS http://localhost:$(APP_PORT)/ready
	@echo ""
	docker compose exec -T db sh -c 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

test-compose:
	npm run test:compose

