Engineering standards for AI coding agents
 
Everything here is a rule, not a suggestion.
 
### 3.1 Repository structure
 
```text
qpath/
├── AGENTS.md                        # These rules (Section 3 of the build plan)
├── knowledge.md                     # One line: "Read AGENTS.md and docs/BUILD_PLAN.md"
├── README.md                        # Setup, architecture summary, SerpApi usage, limits
├── Makefile                         # setup / dev / test / lint / format / record-fixtures
├── LICENSE
├── .gitignore
├── .editorconfig
├── .github/
│   └── copilot-instructions.md      # One line pointing to AGENTS.md
├── docs/
│   ├── BUILD_PLAN.md                # The plan this file comes from
│   ├── ARCHITECTURE.md              # Updated at the end of EVERY phase
│   ├── DATA_AND_METHOD.md           # Honest description of data sources and limits
│   └── DEMO_SCRIPT.md               # Phase 7: 3-minute shot list
├── backend/
│   ├── pyproject.toml               # Dependencies + ruff + pytest config
│   ├── .env.example                 # Every variable, no secrets (committed)
│   ├── .env                         # Real values (NEVER committed)
│   ├── app/
│   │   ├── main.py                  # App factory, router mounting, lifespan (DB init, seed, scheduler)
│   │   ├── core/
│   │   │   ├── config.py            # pydantic-settings Settings: the ONLY place env vars are read
│   │   │   ├── logging.py           # Logging setup (no prints anywhere)
│   │   │   └── errors.py            # Domain exceptions + FastAPI exception handlers
│   │   ├── db/
│   │   │   ├── base.py              # Declarative Base
│   │   │   ├── session.py           # Engine (WAL on), SessionLocal, get_db dependency
│   │   │   └── seed.py              # Idempotent loader for app/data/*.json
│   │   ├── models/                  # SQLAlchemy ORM models, one file per aggregate
│   │   ├── schemas/                 # Pydantic request/response models
│   │   ├── api/
│   │   │   ├── deps.py              # Shared dependencies (db session, admin token check)
│   │   │   └── v1/                  # THIN routers: health, taxonomy, pulse, quiz, profiles,
│   │   │                            #   paths, opportunities, plan, admin, meta + router.py
│   │   ├── services/                # Business logic. No HTTP types, no raw SerpApi/Gemini calls
│   │   ├── integrations/
│   │   │   ├── serpapi/             # client.py (HTTP, fixtures, call cap, logging),
│   │   │   │                        #   parsers.py (raw -> internal), queries.py (query plans)
│   │   │   └── gemini/              # client.py (rate limit, retry, Protocol + fake), prompts.py, schemas.py
│   │   ├── scheduler/
│   │   │   └── jobs.py              # APScheduler job definitions
│   │   └── data/                    # taxonomy.json, career_paths.json, skills_vocab.json,
│   │                                #   quiz_questions.json, resources.json
│   ├── tests/
│   │   ├── conftest.py              # Temp SQLite DB, TestClient, fake LLM fixtures
│   │   ├── fixtures/serpapi/        # Recorded REAL responses (no keys inside)
│   │   ├── unit/                    # Pure functions: parsers, scoring, formulas
│   │   └── integration/             # Endpoints + services against a temp DB
│   └── scripts/
│       ├── record_fixtures.py       # One-off live recording (uses credits)
│       └── seed_demo_history.py     # Phase 7: labeled demo history
└── frontend/
    ├── package.json
    ├── .env.example                 # VITE_API_BASE_URL only
    ├── index.html
    ├── vite.config.ts · tsconfig.json · eslint.config.js · .prettierrc · (Tailwind config per its current docs)
    └── src/
        ├── main.tsx
        ├── app/                     # App.tsx, router.tsx, providers.tsx (QueryClient, error boundary)
        ├── pages/                   # One file per route (thin: compose feature components)
        ├── features/                # pulse/ diagnostic/ paths/ opportunities/ plan/
        │   └── <feature>/           #   components/ hooks/ api.ts types.ts
        ├── components/              # ui/ (buttons, cards, badges) and layout/ (shell, nav)
        ├── lib/                     # apiClient.ts, format.ts, profileId.ts
        ├── types/                   # api.ts: TypeScript mirror of backend schemas
        └── styles/                  # index.css
```
 
### 3.2 Approved stack (do not add anything else without asking and reporting it)
 
**Backend:** Python 3.12; FastAPI; Uvicorn; Pydantic v2 + pydantic-settings; SQLAlchemy 2.x (2.0 style: `select()`, `Mapped[...]`, `mapped_column`); SQLite; `httpx` (sync client); `google-genai`; APScheduler **3.x** (`BackgroundScheduler`; `>=3.10,<4` — 4.x is a different API, never mix); pytest, pytest-cov; ruff (lint + format).
**Frontend:** current Node LTS; Vite; React; TypeScript (strict); React Router; TanStack Query; Tailwind CSS; Recharts; Vitest + React Testing Library; ESLint; Prettier.
 
**Rule:** install the latest stable versions at build time, commit lock files, and follow each library's *current official setup docs*, not memory of older APIs (Tailwind setup, React Router data APIs, TanStack Query v5 object signatures, and the `google-genai` SDK have all changed recently). **Never** use the deprecated `google-generativeai` package.
 
### 3.3 Backend rules
 
1. **Layering is strict:** `api/v1` routers → `services` → (`models`, `integrations`). Routers only parse input, call a service, and return a schema. **No business logic in routers. No DB queries in routers. No raw SerpApi or Gemini calls outside `integrations/`.**
2. **Sync everywhere:** synchronous SQLAlchemy sessions, plain `def` endpoints (FastAPI runs them in a threadpool), sync `httpx.Client`. Do not mix `async def` with blocking calls.
3. **Config:** all env access goes through `core/config.py` `Settings` (typed, validated, cached). No `os.environ` elsewhere. No hardcoded keys, URLs, model names, cron strings or limits.
4. **Schemas vs models:** ORM models never leave the service layer; routers return Pydantic schemas. Request and response models are separate.
5. **Errors:** raise domain exceptions from `core/errors.py` (e.g. `NotFoundError`, `SerpApiError`, `SerpApiCapExceeded`, `LLMOutputError`); central handlers map them to consistent JSON `{ "error": { "code", "message" } }` with correct HTTP status. Never `except: pass`; never swallow exceptions silently; log with context then re-raise or convert.
6. **Logging:** use `logging` via `core/logging.py`. No `print`. **Never log API keys or full request URLs containing them.**
7. **Typing:** full type hints on every function; `ruff` clean; Pydantic for all external data (SerpApi responses are parsed defensively into typed internal objects).
8. **Database:** SQLite with WAL enabled via a connect event; `check_same_thread=False`. Tables are created at startup (`create_all`) — migrations are an intentional non-goal; note it in ARCHITECTURE.md. Background jobs open their **own** session via a context manager; never reuse a request session in a thread.
9. **Idempotency:** ingestion, extraction and seeding must be safe to run repeatedly (upserts, unique constraints, no duplicate rows).
10. **Determinism:** scoring, ranking, gap and plan logic are pure functions with named constants; the LLM never decides a number or a rank.
### 3.4 SerpApi rules
 
1. All SerpApi traffic goes through `integrations/serpapi/client.py`. Nothing else may call `serpapi.com`.
2. Use the REST endpoint `https://serpapi.com/search.json` with `httpx`; **do not** add a SerpApi SDK.
3. Modes: `SERPAPI_USE_FIXTURES=true` reads recorded JSON from `tests/fixtures/serpapi/`; `false` calls live. Live calls are limited by `SERPAPI_DAILY_CALL_CAP` (counted from the call log, UTC day) and raise `SerpApiCapExceeded` beyond it.
4. Every call (live or fixture) is written to `serpapi_call_log` with engine, query, source (`live`/`fixture`), status. The UI's "SerpApi activity" panel reads from it.
5. The API key is passed only as a query parameter at call time, never logged, never stored, never included in fixtures (scrub `api_key` from anything saved).
6. Timeouts: 30 s. Retry once on timeout/5xx; never retry 4xx. A response body containing an `error` field is a `SerpApiError` (except the "no results" message containing "hasn't returned any results", which is treated as a valid empty result and logged with status "empty").
7. **Treat every response field as optional** except what a parser explicitly requires (job: `title`, `company_name`). Use `.get()` with defaults; skip and log malformed items rather than crashing.
8. Google Jobs pagination uses `serpapi_pagination.next_page_token`; never use `start`. `location` and `uule` are mutually exclusive.
9. Do not compute trends from Scholar `total_results`.
### 3.5 Gemini rules
 
1. All LLM calls go through `integrations/gemini/client.py` behind a `StructuredLLM` Protocol so services accept an injected client and tests use a `FakeStructuredLLM`. **No network in tests.**
2. Use `google-genai`: `genai.Client(api_key=...)`, `client.models.generate_content(model=settings.gemini_model, contents=..., config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=<PydanticModel>, temperature=0.1))`. Always pair `response_mime_type` with `response_schema`. Check the current SDK docs if a signature differs.
3. Validate every output with the Pydantic schema **and** domain checks (ids exist in the vocabulary/taxonomy, list lengths match inputs). One retry on invalid output; then mark the item failed. Never trust unvalidated model text.
4. Client-side rate limiting at `GEMINI_REQUESTS_PER_MINUTE`; exponential backoff on 429/5xx (max 3 attempts).
5. Batch extraction (5 postings per call), truncate long descriptions, and **persist results** so each posting is extracted once.
6. Prompts live in `integrations/gemini/prompts.py` as named constants; each states: use only supplied data, never invent numbers/URLs, return null when unknown.
7. The LLM must never generate URLs, salaries, or scores that are shown as facts.
### 3.6 Frontend rules
 
1. TypeScript strict; **no `any`**; no non-null assertions to silence errors. API types live in `src/types/api.ts` and mirror backend schemas.
2. All HTTP goes through `lib/apiClient.ts` (base URL from `import.meta.env.VITE_API_BASE_URL`; normalizes errors). Feature `api.ts` modules wrap endpoints; components never call `fetch` directly.
3. Server state via TanStack Query; local UI state via React state. No global state library.
4. Every data view implements **loading, empty, and error** states.
5. Small components (target < 150 lines), one responsibility each; pages only compose features.
6. Tailwind utilities only; no inline styles; semantic HTML; labels on inputs; visible focus; keyboard operable; sufficient contrast; charts have a text alternative (a table or `aria-label`).
7. No secrets or admin tokens in source. The dev-only admin token is typed into the UI and kept in `sessionStorage`.
8. Format dates/numbers through `lib/format.ts`.
### 3.7 Testing rules
 
1. Backend: `pytest`. Unit tests for pure logic (parsers, scoring, formulas); integration tests for endpoints/services against a **temporary SQLite DB** (never mock the DB). SerpApi tests use recorded fixtures or `httpx.MockTransport`; Gemini tests use `FakeStructuredLLM`.
2. Name tests `test_<unit>_<behavior>`; one behavior per test; table-driven cases where useful.
3. Every bug fix adds a regression test. Every phase adds tests for its new logic; the full suite must pass before a phase is done.
4. Frontend: Vitest + React Testing Library for components with logic and for key flows.
5. A test asserts that no fixture file contains an API key pattern.
### 3.8 Comments and documentation (the owner must be able to understand the code)
 
1. **Every module starts with a short header comment/docstring**: what it is for and where it sits in the flow.
2. **Every public function/class has a docstring**: purpose, arguments, return value, raised errors.
3. Comment the **why**, not the what. Explain non-obvious decisions, edge cases, and any formula (what it means, why those weights, where the constants live).
4. Define domain terms (e.g. "stabilizer code", "decoder", "NISQ") in a short comment where they first matter in code.
5. No commented-out code. No vague comments ("fix this", "magic"). `TODO` must include the phase id: `TODO(phase-5): ...`.
6. React components get a one-line header comment saying what they render and which data they need.
7. Update `docs/ARCHITECTURE.md` at the end of each phase (what was added, data flow, decisions, known limits).
### 3.9 Git rules
 
1. Conventional Commits: `feat(pulse): add posting dedupe`, `fix(serpapi): handle missing description`, `test(...)`, `docs(...)`, `chore(...)`.
2. Commit after every numbered step group — small, reviewable commits. **Judges may read the history.**
3. Never commit `.env`, `*.db`, `.venv`, `node_modules`, `dist`, caches.
4. At phase completion: commit and `git tag phase-N`.
### 3.10 Security rules
 
1. CORS limited to `CORS_ORIGINS`. Admin endpoints require header `X-Admin-Token` compared with `secrets.compare_digest`.
2. Validate all input with Pydantic; use the ORM only (no string-built SQL).
3. `GET /quiz` must **never** include correct answers; scoring happens server-side.
4. Do not store personal data beyond an anonymous profile UUID and the user's own answers.
5. Never print, log, or return secrets. Fixtures are scrubbed.
### 3.11 Things the agent must never do
 
- Add Docker, CI, Alembic, auth, Redis/Celery, or any library outside the approved stack without asking.
- Call SerpApi or Gemini from routers, components, or tests.
- Hardcode model names, keys, limits, URLs, or cron strings.
- Set `"verified": true` on any quiz question (only the owner does).
- Invent SerpApi fields, Gemini behavior, or URLs. If unsure, read the fixture or the official docs.
- Change an earlier phase's public API contract without recording it in `ARCHITECTURE.md` and the final report.
- Touch work belonging to a later phase.
### 3.12 Agent working protocol
 
1. Read `AGENTS.md` and the relevant plan sections. State a short plan and the list of files to create/modify.
2. Implement steps in order; after each step group run `make lint` and `make test`; fix before continuing.
3. If reality differs from the plan (a field is missing, a library API changed), prefer **defensive code + a note in the final report** over guessing.
4. Finish with: acceptance command outputs, updated `ARCHITECTURE.md`, and a report of deviations/assumptions/open questions.
### 3.13 Debug protocol (for Antigravity CLI or any debugging session)
 
1. Reproduce first: write or run a **failing test** that demonstrates the bug.
2. Find the root cause; make the **smallest** fix that addresses it. No drive-by refactors.
3. Confirm the new test passes and the full suite is still green.
4. Explain the cause in the commit body.
### 3.14 Definition of done (every phase)
 
- All numbered steps implemented; acceptance checks pass; `make lint` and `make test` are clean.
- Works in fixture mode with **no keys**, and (where relevant) in live mode with keys.
- `docs/ARCHITECTURE.md` updated; README setup still accurate; commits are clean and tagged.
- Loading, empty and error states exist for every new UI view.
