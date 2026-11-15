.PHONY: setup seed test lint

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
	uv run --locked mypy
	npm run lint:web
	npm run typecheck:web
