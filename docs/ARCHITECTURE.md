# Architecture — Quantum Pathfinder

> Last updated: Phase 2 (Intelligence layer). Updated at the end of every phase per AGENTS.md 3.8.7.

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
 │   health_service, ingestion_service,          │
 │   pulse_service, extraction_service,          │
 │   research_service, (scoring, gap, plan)      │
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
| `backend/app/models/` | ORM models: `job_posting.py` (`JobPosting`, `JobPostingSkill`, `JobPostingSubfield`), `research.py` (`PaperSnapshot`, `ResearchTheme`), `taxonomy.py` (`Subfield`, `Concept`, `CareerPath`, `Skill`) |
| `backend/app/schemas/` | Pydantic request/response models: `pulse.py` (`PulseCard`, `SubfieldDetail`, `SkillShare`, `ThemeOut`), `admin.py`, etc. |
| `backend/app/api/v1/` | Thin routers: parse → call service → return schema. Zero business logic, zero DB queries |
| `backend/app/services/` | All business logic: `pulse_service`, `extraction_service`, `research_service`, `ingestion_service` |
| `backend/app/integrations/serpapi/` | HTTP client (fixture or live), daily cap, call-log writer, query plans, parsers |
| `backend/app/integrations/gemini/` | `StructuredLLM` Protocol, `GeminiStructuredLLM` (google-genai), `FakeStructuredLLM`, prompts, schemas |
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
service calls client.search_jobs(query, fixture_variant=...) / client.search_scholar(query, ...)
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

### Gemini structured LLM flow (Phase 2)

```
service calls llm.generate_structured(prompt, ResponseSchema)
  ├─ FakeStructuredLLM (tests): returns scripted response, no network
  │
  └─ GeminiStructuredLLM (live):
       RateLimiter: sliding 60 s window check (GEMINI_REQUESTS_PER_MINUTE) enforced on every attempt
       Client call: google-genai client.models.generate_content(...)
         response_mime_type="application/json", response_schema=ResponseSchema
       Transport retry: up to 3 attempts (never on 4xx except 429)
         - 429 (quota exhaustion): fixed 30 s backoff (BACKOFF_429_SECONDS) + re-acquire sliding window
         - 5xx (transient overload): short exponential backoff (1 s, 2 s via BACKOFF_5XX_BASE_SECONDS)
       Schema validation: validate with Pydantic; retry once with error feedback on failure, then LLMOutputError
```

### Extraction & Research pipelines (Phase 2)

```
1. Job Skill Extraction (POST /admin/extract):
   - Select postings with status in (pending, failed) and attempts < 3 (batches of 5)
   - Truncate job descriptions to ~3000 chars
   - Injected LLM extracts skills against controlled vocabulary and identifies seniority/PhD
   - Domain post-validation: drop unmapped skills, align posting refs
   - Persist to job_posting_skills and update job_postings (status=done)

2. Scholar Research Refresh (POST /admin/refresh/scholar):
   - Run Scholar query plan per subfield (scisbd=1, num=20, recent)
   - Parse defensive paper metadata (title required, extract 19xx/20xx publication year)
   - total_results is deliberately ignored (no trends computed from Scholar)
   - Store PaperSnapshot records with batch_id UUID
   - Generate qualitative research themes (3–5 themes, strictly grounded in papers)
   - Validate 1-based paper indexes; store ResearchTheme records
```

### Market Pulse intelligence (Phase 2)

```
GET /pulse:
   Returns 6 PulseCards, each extended additively with top_skills[:5] and themes[:3].

GET /pulse/{subfield_id}:
   Returns SubfieldDetail:
   - Full top_skills list with exact mention share among extracted postings
   - Seniority mix breakdown (including "unknown" bucket for NULL/unspecified)
   - PhD requirement share among postings specifying the requirement
   - Extraction coverage ratio (extracted postings / total active postings)
   - Research themes with titles and URLs of supporting papers
   - Paginated postings list
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
SerpApi returns `{"error": "Google hasn't returned any results for this query."}` for valid queries with zero results — this is **not** a real error. `SerpApiClient` detects the phrase `"hasn't returned any results"` and treats such responses as valid empty results, logging status `"empty"`. Phase 1 parsers handle a missing `jobs_results` / `organic_results` key as zero items.

### Demand fairness via core-tier query counting
The job query plan has unequal query counts per subfield (e.g. `hardware` has 4 queries, while `qml` has 1). To keep the demand signal fair, only postings found via a CORE-tier query count toward a subfield's headline and demand figures (`active_s` and `PulseCard.active_postings`). Postings discovered only through extended-tier queries are tracked separately in `PulseCard.extra_postings` and remain accessible in posting lists and for skill extraction without inflating comparative demand metrics. If a posting is found by both tiers for the same subfield, the `core` tier is retained in `job_posting_subfields`.

### Two-layer validation split (LLM client vs service)
The `StructuredLLM` client performs technical schema validation (Pydantic parsing + one schema-correction retry). The `extraction_service` and `research_service` perform domain validation: dropping unmapped skills, ensuring array lengths match inputs, aligning IDs to the seeded vocabulary, and verifying 1-based paper snapshot indexes. This cleanly separates transport/protocol contracts from business integrity.

### Skills and mix computed over all linked active postings
While headline demand counts only reflect core-tier queries for fairness, skill shares, seniority mix, and extraction coverage are computed across ALL active postings linked to a subfield in that region (both core and extended tiers). This provides the richest skill vocabulary signal available from the collected corpus.

### Research themes served from newest batch only
Research snapshots are saved in versioned batches per run (UUID `batch_id`). Only the latest batch's themes are served on pulse cards and detail pages. Historical batches remain stored for demo auditability without creating synthetic trend numbers.

### PulseCard additive contract change
In Phase 2, `PulseCard` schema was extended additively with `top_skills: list[SkillShare] = []` and `themes: list[ThemeOut] = []`. Defaulting to empty lists ensures that Phase 1 consumers, fixtures, and tests remain completely backwards-compatible while Phase 2 UI renders the new intelligence layers when data is present.

---

## Known limits

- **No Alembic / migrations:** a schema change requires dropping and recreating the database. Development databases are not committed (`backend/data/` is gitignored).
- **SerpApi sampling:** page-capped ingestion means posting counts are sampled, not exhaustive. The UI shows a "low data" badge when `active_postings < 8` (Phase 1).
- **Scholar total_results not used:** erratic across re-runs; qualitative themes only. A regression test enforces that neither models nor parsers process this field.
- **Extraction attempt cap:** postings that fail LLM extraction twice are flagged `failed` with attempts incremented. Candidates reaching 3 attempts are excluded from further background selection.
- **Extraction coverage caveat:** skill shares are proportions of extracted postings (`done`), not total corpus postings. Detail views display the extraction coverage metric and caveat estimated shares when coverage < 100%.
- **Scheduler off by default:** `SCHEDULER_ENABLED=false`. Enable only for the demo or final days (Phase 5).
- **httpx2 warning:** benign StarletteDeprecationWarning from starlette.testclient.

