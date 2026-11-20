.PHONY: setup seed dev test lint e2e benchmark smoke reset-demo compose-setup compose-seed compose-dev compose-test compose-lint compose-e2e compose-benchmark compose-smoke compose-reset-demo

setup:
	uv sync --locked
	npm ci

seed:
	uv run --locked python scripts/seed.py

test:
	uv run --locked pytest
	npm run test:web

lint:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked mypy
	npm run lint:web
	npm run typecheck:web

dev:
	uv run --locked python scripts/dev.py

e2e:
	npm run e2e

benchmark:
	uv run --locked python scripts/benchmark.py --output test-results/benchmark.json

smoke:
	uv run --locked python scripts/smoke.py

reset-demo:
	uv run --locked python scripts/reset_demo.py

compose-setup:
	docker compose --profile qa build

compose-dev:
	docker compose up --build

compose-seed:
	docker compose run --rm --no-deps api python scripts/seed.py --check

compose-test:
	docker compose run --rm qa sh -ec 'pytest && npm run test:web'

compose-lint:
	docker compose run --rm qa sh -ec 'ruff check . && ruff format --check . && mypy && npm run lint:web && npm run typecheck:web'

compose-e2e:
	docker compose run --rm qa npm run e2e

compose-benchmark:
	docker compose run --rm qa python scripts/benchmark.py --output test-results/benchmark.json

compose-smoke:
	docker compose run --rm qa python scripts/smoke.py

compose-reset-demo:
	docker compose stop web api
	docker compose run --rm --no-deps api python scripts/reset_demo.py
