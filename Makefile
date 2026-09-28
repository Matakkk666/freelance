# Single entry point for every routine command. `make help` lists targets.
# Agents and CI use these targets instead of calling tools directly.

SHELL := /bin/bash
BACKEND := backend
FRONTEND := frontend
UV := cd $(BACKEND) && uv run --locked
PNPM := pnpm --dir $(FRONTEND)

.DEFAULT_GOAL := help
.PHONY: help setup install db-up migrate migration dev dev-backend dev-frontend \
	format lint typecheck test check \
	backend-lint backend-typecheck backend-test \
	frontend-lint frontend-typecheck frontend-test frontend-build

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

setup: ## Full idempotent setup: PostgreSQL, .env, dependencies, migrations
	./scripts/setup-sandbox.sh

install: ## Install backend (uv) and frontend (pnpm) dependencies from lockfiles
	cd $(BACKEND) && uv sync --locked
	$(PNPM) install --frozen-lockfile

db-up: ## Start PostgreSQL via docker compose (alternative to `make setup` on a machine with Docker)
	docker compose up -d --wait db

migrate: ## Apply migrations to DATABASE_URL
	$(UV) alembic upgrade head

migration: ## Create a migration: make migration name="add ledger" rev=0002
	@test -n "$(name)" -a -n "$(rev)" || (echo 'usage: make migration name="short description" rev=000N' && exit 1)
	$(UV) alembic revision --autogenerate --rev-id "$(rev)" -m "$(name)"

dev: ## Run backend and frontend dev servers together
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend: ## Backend with autoreload on :8000
	$(UV) uvicorn app.asgi:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Frontend (Vite) on :5173, proxies /api and /health to :8000
	$(PNPM) dev --host 0.0.0.0 --port 5173

format: ## Auto-format and auto-fix backend and frontend
	$(UV) ruff format .
	$(UV) ruff check --fix .
	$(PNPM) format

lint: backend-lint frontend-lint ## Linters and format checks only
typecheck: backend-typecheck frontend-typecheck ## Type checks only
test: backend-test frontend-test ## Tests only (backend needs PostgreSQL)

check: lint typecheck test frontend-build ## Everything CI runs. Must pass before every PR
	@echo "make check: all checks passed"

backend-lint:
	$(UV) ruff format --check .
	$(UV) ruff check .

backend-typecheck:
	$(UV) mypy

backend-test:
	$(UV) pytest

frontend-lint:
	$(PNPM) lint

frontend-typecheck:
	$(PNPM) typecheck

frontend-test:
	$(PNPM) test

frontend-build:
	$(PNPM) build
