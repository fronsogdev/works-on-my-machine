# Single entry point for local development. Every documented command is a
# target here; the README and runbook only point at these targets.
.DEFAULT_GOAL := help

UV := uv
COMPOSE := docker compose

.PHONY: help install lint format test coverage migrate api worker \
        build build-compare up down clean

help: ## Show the available targets
	@echo "Works On My Machine -- available targets:"
	@echo "  make install        Create the uv env and install dependencies"
	@echo "  make up             Build and start the full local stack (compose)"
	@echo "  make down           Stop the local stack, keeping named volumes"
	@echo "  make clean          Stop the stack and delete its named volumes"
	@echo "  make build          Build the api and worker images"
	@echo "  make build-compare  Build naive vs real images and print the size table"
	@echo "  make lint           ruff check + ruff format --check + mypy"
	@echo "  make format         Auto-fix and format with ruff"
	@echo "  make test           pytest with coverage, fails under 80% (no Docker needed)"
	@echo "  make coverage       pytest with an HTML coverage report in htmlcov/"
	@echo "  make migrate        Apply Alembic migrations (needs a reachable database)"
	@echo "  make api            Run the API with autoreload (needs Postgres + Redis)"
	@echo "  make worker         Run an RQ worker (needs Postgres + Redis)"

install: ## Create the uv env and install dependencies
	$(UV) sync

up: ## Build and start the full local stack
	$(COMPOSE) up -d --build

down: ## Stop the local stack, keeping named volumes
	$(COMPOSE) down

clean: ## Stop the stack and delete its named volumes
	$(COMPOSE) down -v --remove-orphans

build: ## Build the api and worker images
	$(COMPOSE) build api worker

build-compare: ## Build naive vs real images and print the size/layer table
	./docker/compare-images.sh

lint: ## Lint, format-check and type-check
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy app worker tests migrations

format: ## Auto-fix and format with ruff
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

test: ## Run the test suite with coverage (Docker not required)
	$(UV) run pytest --cov=app --cov=worker --cov-report=term-missing --cov-report=html --cov-fail-under=80

coverage: ## Run tests and write an HTML coverage report
	$(UV) run pytest --cov=app --cov=worker --cov-report=term --cov-report=html

migrate: ## Apply Alembic migrations to WOMM_DATABASE_URL
	$(UV) run alembic -c migrations/alembic.ini upgrade head

api: ## Run the API with autoreload
	$(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run an RQ worker
	$(UV) run python -m worker.worker
