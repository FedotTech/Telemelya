.PHONY: local-up local-down test test-report

local-up:
	docker compose -f docker-compose.local.yml up -d

local-down:
	docker compose -f docker-compose.local.yml down -v

test:
	behave tests/features/

test-report:
	behave tests/features/ -f allure_behave.formatter:AllureFormatter -o allure-results
	allure serve allure-results
