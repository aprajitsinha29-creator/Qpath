# Quantum Pathfinder — developer entry points (docs/BUILD_PLAN.md, Phase 0 step 0.1.3).
# All Python runs go through backend/.venv; the system pip is externally managed on
# this machine, so `setup` always builds a project-local venv first.

VENV := backend/.venv

.PHONY: setup dev-backend dev-frontend test lint format record-fixtures seed-demo

setup: ## Create backend/.venv, install the backend (editable + dev extras), install frontend deps if present
	python3 -m venv $(VENV)
	cd backend && .venv/bin/pip install -e ".[dev]"
	@if [ -d frontend ]; then (cd frontend && npm ci || npm install); else echo "frontend/ not present yet (Phase 0 step 0.6) — skipping npm install"; fi

dev-backend: ## Run the API with auto-reload on http://localhost:8000
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run the Vite dev server (needs frontend/, Phase 0 step 0.6)
	@if [ -d frontend ]; then cd frontend && npm run dev; else echo "frontend/ not present yet (Phase 0 step 0.6)" && exit 1; fi

test: ## Backend pytest; frontend vitest when frontend/ exists
	cd backend && .venv/bin/pytest
	@if [ -d frontend ]; then (cd frontend && npm run --if-present test -- --run); else echo "frontend/ not present yet — skipping frontend tests"; fi

lint: ## Ruff lint + format check on the backend; frontend lint when present
	cd backend && .venv/bin/ruff check .
	cd backend && .venv/bin/ruff format --check .
	@if [ -d frontend ]; then (cd frontend && npm run --if-present lint); else echo "frontend/ not present yet — skipping frontend lint"; fi

format: ## Auto-fix lint issues and rewrite formatting
	cd backend && .venv/bin/ruff check --fix .
	cd backend && .venv/bin/ruff format .
	@if [ -d frontend ]; then (cd frontend && npm run --if-present lint && npm run --if-present format); fi

record-fixtures: ## Record live SerpApi fixtures (spends credits; extra args via ARGS=--force)
	cd backend && .venv/bin/python scripts/record_fixtures.py $(ARGS)

seed-demo: ## Labeled demo history (Phase 7)
	@echo "seed-demo: scripts/seed_demo_history.py arrives with Phase 7"
