# Architecture — Quantum Pathfinder

> Last updated: Phase 0 (Foundation). Updated at the end of every phase per AGENTS.md 3.8.7.

---

## Overview

Quantum Pathfinder is a live-data career navigator for quantum computing. It pairs real job-market data (via SerpApi Google Jobs and Google Scholar) with deterministic scoring and structured AI output (Gemini) to deliver personalised career path recommendations and skill-gap plans.

---

## Layer diagram

```
Browser (React / Vite)
        │  HTTP/JSON
        ▼
FastAPI  /api/v1
        │
 ┌──────┴──────────────────┐
 │  routers (thin)         │  parse → call one service → return Pydantic schema
 └──────┬──────────────────┘
        │
        ▼
 ┌──────────────────────────────────────────────┐
 │  services/                                    │  all business logic lives here
 │   health_service, (ingestion, pulse,          │
 │    extraction, research, scoring, gap, plan)  │
 └──────┬──────────────────┬────────────────────┘
        │                  │
        ▼                  ▼
 ┌───────────┐    ┌─────────────────────────────┐
 │  models/  │    │  integrations/               │
 │  (SQLite) │    │   serpapi/client.py (fixture │
 │           │    │     or live, daily cap, log) │
 │  WAL mode │    │   gemini/client.py (Protocol,│
 │  create_  │    │     fake, rate-limit, retry) │
 │  all at   │    └─────────────────────────────┘
 │  startup  │
 └───────────┘

Optional (Phase 5):
 scheduler/ (APScheduler 3.x BackgroundScheduler)
   ↓ calls ingestion + research services on cron
```

---

## Folder responsibilities

| Path | Responsibility |
|---|---|
| `backend/app/core/config.py` | **Only** place env vars are read (pydantic-settings `Settings`); fail-fast validators |
| `backend/app/core/logging.py` | Logging setup; no `print` anywhere else in the codebase |
| `backend/app/core/errors.py` | Domain exceptions + central FastAPI exception handlers; uniform JSON error shape |
| `backend/app/db/base.py` | SQLAlchemy `DeclarativeBase` |
| `backend/app/db/session.py` | Engine (SQLite WAL), `SessionLocal`, `get_db` dependency |
| `backend/app/db/seed.py` | Idempotent upsert loader for `app/data/*.json`; validates references and prerequisite DAG at startup |
| `backend/app/models/` | ORM models (one file per aggregate, SQLAlchemy 2.0 style with `Mapped[...]`) |
| `backend/app/schemas/` | Pydantic request/response models (ORM models never leave the service layer) |
| `backend/app/api/v1/` | Thin routers: parse → call service → return schema. Zero business logic, zero DB queries |
| `backend/app/services/` | All business logic (scoring, aggregation, seed helpers). No HTTP types, no raw SerpApi/Gemini calls |
| `backend/app/integrations/serpapi/` | HTTP client (fixture or live), daily cap, call-log writer, query plans |
| `backend/app/integrations/gemini/` | Phase 2+. `StructuredLLM` Protocol + real impl + `FakeStructuredLLM` for tests |
| `backend/app/scheduler/` | Phase 5+. APScheduler job definitions (each opens its own DB session) |
| `backend/app/data/` | Committed reference JSON: `taxonomy.json`, `career_paths.json`, `skills_vocab.json`, `quiz_questions.json`, `resources.json` |
| `backend/tests/fixtures/serpapi/` | Real recorded SerpApi responses (no API keys); read in fixture mode |
| `frontend/src/lib/apiClient.ts` | All frontend HTTP goes here; normalises backend error shape into `ApiError` |
| `frontend/src/types/api.ts` | TypeScript mirrors of backend Pydantic schemas (no `any`) |
| `frontend/src/features/<name>/` | Feature co-location: `api.ts`, `types.ts`, `components/`, `hooks/` |
| `frontend/src/components/` | Shared UI components (`ui/`) and layout (`layout/AppShell`) |
| `frontend/src/lib/format.ts` | All date/number formatting — never inline |
| `frontend/src/lib/profileId.ts` | Anonymous profile UUID in `localStorage` |

---

## Data flow

### Request lifecycle (Phase 0)

```
Browser → GET /api/v1/health
            → health router (no logic)
            → health_service.get_health_report(db)
                → SELECT 1  (db probe)
            ← HealthResponse {status, version, env, db}
            ← JSON 200
```

### SerpApi client flow

```
service calls client.search_jobs(query, fixture_variant=...)
  ├─ SERPAPI_USE_FIXTURES=true
  │    read tests/fixtures/serpapi/<engine>__<slug>__<variant>.json
  │    write serpapi_call_log row (source=fixture)
  │
  └─ SERPAPI_USE_FIXTURES=false
       check today's live count against SERPAPI_DAILY_CALL_CAP
       GET https://serpapi.com/search.json  (api_key as query param only; 30s timeout; 1 retry on 5xx)
       error body → SerpApiError  (except "hasn't returned any results" → empty result)
       write serpapi_call_log row (source=live)
```

### Seed flow (startup)

```
app lifespan
  → SQLAlchemy create_all (no Alembic — intentional; see Decision Log)
  → seed_reference_data(db)
      load taxonomy.json, career_paths.json, skills_vocab.json
      validate: all ids resolve, concept DAG is acyclic, skill subfields exist
      upsert subfields → concepts → career_paths → skills (idempotent)
```

---

## Decision log

### Sync stack (no async)
Endpoints are plain `def` (FastAPI runs them in a threadpool), SQLAlchemy sessions are synchronous, and `httpx.Client` is synchronous. This avoids the `async def` + blocking-call pitfall and is fully sufficient for the expected request volume. If async becomes necessary in a future phase it will be recorded here.

### SQLite + `create_all` (no Alembic)
Using SQLite with WAL mode enabled via a connect event. Tables are created with `create_all` at startup. Migrations are an intentional non-goal for this hackathon build; if the schema changes, the database file is deleted and recreated (noted in `README.md`).

### Fixtures-first SerpApi
`SERPAPI_USE_FIXTURES=true` is the default. All tests run offline against recorded fixtures. The daily call cap and fixture recording script exist to make live-mode safe and auditable.

### SerpApi empty results
SerpApi returns `{"error": "Google hasn't returned any results for this query."}` for valid queries with zero results — this is **not** a real error. `SerpApiClient` detects the phrase `"hasn't returned any results"` and treats such responses as valid empty results, logging status `"empty"`. Phase 1 parsers must handle a missing `jobs_results` / `organic_results` key as zero items.

The committed fixture `google_jobs__quantum-error-correction__india_p1.json` is a real empty-result response kept as a deliberate test case for this path.

### No migrations
Schema changes drop and recreate the database. This is explicitly noted so future agents do not add Alembic (prohibited in AGENTS.md 3.11).

### Tailwind v4
Uses `@tailwindcss/vite` plugin (not the old PostCSS/`tailwind.config.js` approach). The CSS entrypoint imports `tailwindcss` directly with `@import "tailwindcss"`.

### httpx2 deprecation warning
Starlette 1.7.0 (shipped with FastAPI 0.142.2) emits `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead`. The fix requires adding `httpx2` as a dev dependency. Because `httpx2` is not in the approved stack (AGENTS.md 3.2) and adding it requires owner approval, it is **not installed**. All 40 backend tests pass; the warning is benign. This is documented here so the next agent does not re-investigate.

### Demand fairness via core-tier query counting
The job query plan has unequal query counts per subfield (e.g. `hardware` has 4 queries, while `qml` has 1). To keep the demand signal fair, only postings found via a CORE-tier query count toward a subfield's headline and demand figures (`active_s` and `PulseCard.active_postings`). Postings discovered only through extended-tier queries are tracked separately in `PulseCard.extra_postings` and remain accessible in posting lists and for skill extraction without inflating comparative demand metrics. If a posting is found by both tiers for the same subfield, the `core` tier is retained in `job_posting_subfields`.

---

## Known limits

- **No Alembic / migrations:** a schema change requires dropping and recreating the database. Development databases are not committed (`backend/data/` is gitignored).
- **SerpApi sampling:** page-capped ingestion means posting counts are sampled, not exhaustive. The UI will show a "low data" badge when `active_postings < 8` (Phase 1).
- **Scholar total_results not used:** erratic across re-runs; qualitative themes only (Section 1.5 of BUILD_PLAN.md).
- **Gemini not configured:** Phase 0 has no LLM calls. `GEMINI_API_KEY` and `GEMINI_MODEL` are optional until Phase 2.
- **Scheduler off by default:** `SCHEDULER_ENABLED=false`. Enable only for the demo or final days (Phase 5).
- **httpx2 warning:** see Decision Log above.
