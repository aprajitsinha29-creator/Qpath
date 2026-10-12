# Makefile — QPath developer entry points (docs/BUILD_PLAN.md, Phase 0 step 0.1.3).
# All Python runs go through backend/.venv; the system pip is externally managed on
# this machine, so `setup` always builds a project-local venv first.
#
# Targets:
#   setup            — create venv, install backend (editable + dev), install frontend npm deps
#   dev-backend      — run API at http://localhost:8000 (auto-reload)
#   dev-frontend     — run Vite dev server at http://localhost:5173
#   test             — backend pytest + frontend vitest (--run, non-interactive)
#   lint             — ruff check + format-check on backend; eslint + prettier-check on frontend
#   format           — auto-fix backend with ruff; auto-format frontend with prettier
#   record-fixtures  — record live SerpApi fixtures (spends credits; manual task M-06 only)
#   seed-demo        — load labelled demo history (Phase 7)

VENV := backend/.venv

.PHONY: setup dev-backend dev-frontend test lint format record-fixtures seed-demo

setup: ## Create backend/.venv, install the backend (editable + dev extras), install frontend deps
	python3 -m venv $(VENV)
	cd backend && .venv/bin/pip install -e ".[dev]"
	@if [ -d frontend ]; then \
		cd frontend && npm ci; \
	else \
		echo "frontend/ not present yet — skipping npm install"; \
	fi

dev-backend: ## Run the API with auto-reload on http://localhost:8000
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run the Vite dev server at http://localhost:5173 (needs frontend/)
	@if [ -d frontend ]; then \
		cd frontend && npm run dev; \
	else \
		echo "frontend/ not present yet (Phase 0 step 0.6)" && exit 1; \
	fi

test: ## Backend pytest; frontend vitest (--run, non-interactive) when frontend/ exists
	cd backend && .venv/bin/pytest
	@if [ -d frontend ]; then \
		cd frontend && npm run test -- --run; \
	else \
		echo "frontend/ not present yet — skipping frontend tests"; \
	fi

lint: ## Ruff lint + format-check on the backend; eslint + prettier-check on the frontend
	cd backend && .venv/bin/ruff check .
	cd backend && .venv/bin/ruff format --check .
	@if [ -d frontend ]; then \
		cd frontend && npm run lint; \
	else \
		echo "frontend/ not present yet — skipping frontend lint"; \
	fi

format: ## Auto-fix lint issues and rewrite formatting
	cd backend && .venv/bin/ruff check --fix .
	cd backend && .venv/bin/ruff format .
	@if [ -d frontend ]; then \
		cd frontend && npm run format; \
	fi

record-fixtures: ## Record live SerpApi fixtures (spends credits; extra args via ARGS=--force)
	cd backend && .venv/bin/python scripts/record_fixtures.py $(ARGS)

seed-demo: ## Labeled demo history (Phase 7)
	@echo "seed-demo: scripts/seed_demo_history.py arrives with Phase 7"
