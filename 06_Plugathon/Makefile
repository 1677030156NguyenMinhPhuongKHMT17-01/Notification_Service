.PHONY: install verify-contracts lint config build up up-external down down-clean ps logs readiness sim e2e test-plugathon

APP_PORT ?= 8000

install:
	npm ci

verify-contracts:
	python scripts/verify_frozen_contracts.py

lint:
	npm run lint:openapi

config:
	docker compose config --quiet
	docker compose -f docker-compose.yml -f docker-compose.external-broker.yml config --quiet

build:
	docker compose build

up:
	docker compose up -d --build --wait

up-external:
	docker compose -f docker-compose.yml -f docker-compose.external-broker.yml up -d --build --wait

down:
	docker compose down

down-clean:
	docker compose down -v

ps:
	docker compose ps

logs:
	docker compose logs -f

readiness:
	curl -fsS http://localhost:$(APP_PORT)/health
	@echo ""
	curl -fsS http://localhost:$(APP_PORT)/ready
	@echo ""
	docker compose exec -T db sh -c 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

sim:
	python scripts/core_business_simulator.py --scenario all

e2e:
	python scripts/run_plugathon_e2e.py --with-compose-dlq-recovery

test-plugathon:
	npm run test:plugathon
