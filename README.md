# Quantum Pathfinder

> A live-data career navigator for quantum computing. Quantum Pathfinder measures what you know, shows where the quantum job market and research are moving, recommends the career paths that fit you, and keeps tracking opportunities for the path you choose.

Built for the **SerpApi India Hackathon 2026** (deadline: Oct 10, 2026, 23:59 IST).

---

## Quick start (two commands)

```bash
make setup     # create backend/.venv, install all deps, npm ci for frontend
```

Copy env files, then start both servers in separate terminals:

```bash
cp backend/.env.example backend/.env   # fill SERPAPI_API_KEY (optional for fixture mode)
cp frontend/.env.example frontend/.env

make dev-backend      # http://localhost:8000
make dev-frontend     # http://localhost:5173
```

Open `http://localhost:5173`. You should see the app shell with a **"Backend: OK"** badge.

---

## Environment variables

All backend configuration is read from `backend/.env` (copy `backend/.env.example`).
All frontend configuration is read from `frontend/.env` (copy `frontend/.env.example`).

### Backend (`backend/.env.example`)

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Runtime environment name (shown in `/health`) |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `DATABASE_URL` | `sqlite:///./data/pathfinder.db` | SQLite path; `backend/data/` is gitignored |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed origins for browser requests |
| `ADMIN_TOKEN` | `change-me` | Token required for `X-Admin-Token` header on admin endpoints |
| `SERPAPI_API_KEY` | *(empty)* | SerpApi key — only needed when `SERPAPI_USE_FIXTURES=false` |
| `SERPAPI_USE_FIXTURES` | `true` | `true` = read recorded JSON, spend no credits |
| `SERPAPI_DAILY_CALL_CAP` | `60` | Hard stop for live calls per UTC day |
| `SERPAPI_JOBS_MAX_PAGES` | `3` | Max pages per query in bootstrap mode |
| `GEMINI_API_KEY` | *(empty)* | Gemini API key — required for Phase 2+ extraction |
| `GEMINI_MODEL` | *(empty)* | Model id, e.g. `gemini-2.5-flash` |
| `GEMINI_REQUESTS_PER_MINUTE` | `5` | Client-side rate limit (conservative free-tier default) |
| `SCHEDULER_ENABLED` | `false` | Keep `false` during development (Phase 5) |
| `JOBS_DAILY_CRON` | `0 3 * * *` | Daily global job refresh cron (Phase 5) |
| `JOBS_INDIA_WEEKLY_CRON` | `0 4 * * 1` | Weekly India job refresh cron (Phase 5) |
| `SCHOLAR_WEEKLY_CRON` | `0 5 * * 1` | Weekly Scholar refresh cron (Phase 5) |
| `ALLOW_UNVERIFIED_QUESTIONS` | `false` | `true` only while building quiz UI (Phase 3) |
| `DEMO_MODE` | `false` | Serve labelled demo history in Phase 7 |

### Frontend (`frontend/.env.example`)

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | FastAPI base URL used by `lib/apiClient.ts` |

**Security:** `backend/.env` is gitignored and must never be committed. `SERPAPI_USE_FIXTURES=true` (the default) lets you develop and run the full test suite with no API keys.

---

## Project structure

```
Qpath/
├── Makefile                     # All developer entry points
├── backend/
│   ├── pyproject.toml           # Python deps, ruff, pytest config
│   ├── .env.example             # Template — copy to .env, fill real values
│   ├── app/
│   │   ├── main.py              # App factory; lifespan creates tables + seeds DB
│   │   ├── core/                # config.py, logging.py, errors.py
│   │   ├── db/                  # base.py, session.py (WAL), seed.py
│   │   ├── models/              # SQLAlchemy ORM models (one file per aggregate)
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── api/v1/              # Thin routers: health, (more in later phases)
│   │   ├── services/            # Business logic (no HTTP types, no raw API calls)
│   │   ├── integrations/
│   │   │   ├── serpapi/         # client.py, queries.py (fixture + live modes)
│   │   │   └── gemini/          # Phase 2: client.py, prompts.py, schemas.py
│   │   ├── scheduler/           # Phase 5: APScheduler jobs
│   │   └── data/                # taxonomy.json, career_paths.json, skills_vocab.json, …
│   └── tests/
│       ├── fixtures/serpapi/    # Real recorded responses (no keys)
│       ├── integration/         # Endpoint tests against a temp SQLite DB
│       └── unit/                # Parser, seeder, scoring, formula tests
└── frontend/
    ├── package.json             # React 19, Vite 7, TypeScript strict, Tailwind v4
    ├── src/
    │   ├── app/                 # App.tsx, router.tsx, providers.tsx
    │   ├── features/            # health/ (HealthBadge) — more in later phases
    │   ├── components/layout/   # AppShell (header, nav, footer)
    │   ├── lib/                 # apiClient.ts, format.ts, profileId.ts
    │   ├── pages/               # PulsePage, MethodPage, NotFoundPage
    │   └── types/api.ts         # TypeScript mirrors of backend schemas
```

---

## SerpApi usage

Quantum Pathfinder uses two SerpApi engines:

- **Google Jobs** (`engine=google_jobs`) — ingests quantum job postings per subfield (global and India) to power the Market Pulse, career path demand scores, and opportunity tracking.
- **Google Scholar** (`engine=google_scholar`) — fetches recent papers per subfield (`scisbd=1`) to generate qualitative research themes via Gemini.

The API key is passed only at call time; it is never logged, stored, or committed. Set `SERPAPI_USE_FIXTURES=true` (default) to work offline using the recorded fixtures in `backend/tests/fixtures/serpapi/`.

---

## Status

| Phase | Description | Status |
|---|---|---|
| **0** | Foundation: backend API, health endpoint, SerpApi client in fixture mode, frontend shell with HealthBadge | ✅ **Done** |
| **1** | Market Pulse v1: six subfield cards with live/fixture job counts | ✅ **Done** |
| **2** | Intelligence layer: Gemini skill extraction + Scholar research themes | ✅ **Done** |
| **3** | Orientation diagnostic: quiz + readiness radar | ✅ **Done** |
| **4** | Path matcher: deterministic ranked career paths + grounded explanations + /paths UI (incl. carry-over: declared-skills picker, `PUT /profiles/{id}/skills`, `GET /skills`) | ✅ **Done** |
| 5 | Opportunity tracker: scheduler, matched postings, is_new badges | 🔜 |
| 6 | Gap analysis & learning plan | 🔜 |
| 7 | Submission hardening: method page, demo script, secret scan | 🔜 |

---

## Development commands

```bash
make setup            # One-time setup
make dev-backend      # Backend dev server (auto-reload)
make dev-frontend     # Frontend dev server
make test             # Run all tests (backend + frontend)
make lint             # Lint check (ruff + eslint + prettier)
make format           # Auto-format all code
```

**Tests run in fixture mode** — no API keys required. The full suite passes with `make test` from a clean clone after `make setup`.