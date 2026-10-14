# AGENTS.md

## What this repo is

Works On My Machine™ Certification Authority: a small FastAPI + RQ + Pillow app that issues joke certificates, built as a production-grade DevOps showcase (Docker, CI/CD, IaC, supply chain security, observability). The app stays small; the infrastructure is the point.

## Read first

- `PLAN.md` — scope, locked decisions, trade-offs, cost table, phase-by-phase acceptance criteria. Read before starting any phase.
- `README.md` — the public pitch, quick start, cost breakdown. Keep it in sync with reality.
- `docs/runbook.md` — deploy, rollback, secret rotation, debugging. Consult before any cloud operation.

## Ground rules

- The repository must read as fully human-maintained: no tool fingerprints, no assistant or model names, no chat transcripts, no prompt or session files, no local machine paths in any committed file, commit message, PR, or release note.
- The Makefile is the single entry point for everything. Documented commands are make targets, nothing else.
- No secrets in git, in images, or in GitHub settings. Cloud access happens through short-lived OIDC tokens only.
- Honesty over theater: costs, manual steps, and flaky behavior are stated and documented. Never invent results or fake screenshots.
- Conventional commits, small and logical, one concern per commit.
- Anything that costs money gets a warning before it is used, and must be removable with `make destroy`.

## Stack

Python 3.12, uv, FastAPI, SQLAlchemy 2.0 + Alembic, RQ + Redis, Pillow, prometheus-client, pytest, ruff, mypy, Docker, docker-compose, GitHub Actions (SHA-pinned), Terraform + tflint, cosign/Trivy/Syft, k6, Prometheus + Grafana. Cloud: GCP Cloud Run (`us-central1`), Neon Postgres, Upstash Redis, ghcr.io.

## Commands

Run `make help` for the full list; the canonical set is:

- `make install` — create the venv with uv and install dev dependencies
- `make up` / `make down` — start/stop the full local stack (compose)
- `make test` / `make lint` — pytest with coverage, then ruff + mypy
- `make build` / `make build-compare` — build images, or build naive vs. real and print the comparison table
- `make deploy-staging` / `make deploy-prod` — terraform + Cloud Run deploys (CI does this; manual use is for debugging)
- `make destroy` — tear down every cloud resource Terraform created
- `make chaos` — run the chaos profile during a k6 load test

If a make target is missing or stale, fix the Makefile, do not document a workaround.

## Conventions

- Type hints on all public functions; pydantic-settings for configuration; structlog JSON logging; graceful shutdown in the API and worker.
- ruff is the single linter and formatter; mypy must be clean; both run in pre-commit.
- Tests: unit tests use fakeredis and never touch the network; API tests use httpx AsyncClient; anything that needs real Postgres is a testcontainers integration test. Keep core-logic coverage ≥ 80%.
- Migrations via Alembic only; never hand-edit applied migrations. One migration per model change.
- Dockerfiles: multi-stage, non-root, read-only rootfs with a tmpfs for `/tmp`, HEALTHCHECK. No secrets in build args or layers.
- Actions pinned by full commit SHA; least-privilege `permissions:` per job; concurrency groups on deploy workflows.

## Workflow

- Work phase by phase, in `PLAN.md` order. A phase is done only when its stated acceptance criteria pass locally — check them, do not assume.
- After each phase: summarize what was built, how to run and verify it, then stop and wait.
- Before any change to cloud state: read the runbook section for it, run `terraform plan`, and never apply to prod outside the deploy pipeline.
