.PHONY: install lint test-queue mock mock-notify mock-core mock-all test-mock test-local test-html test-ci clean

install:
	npm install

lint:
	npm run lint:contracts

test-queue:
	npm run test:queue

mock: mock-notify

mock-notify:
	npm run mock:notify

mock-core:
	npm run mock:core

mock-all:
	bash scripts/start-prism-mock.sh all

test-mock:
	npm run test:mock

test-local:
	npm run test:local

test-html:
	npm run test:html

test-ci:
	npm run test:ci

clean:
	rm -f reports/*.xml reports/*.html reports/*.json prism*.log
