# QPath — Project Summary

> A live-data career navigator for quantum computing, built for the **SerpApi India Hackathon 2026**.
> Generated: 12 October 2026.

---

## 1. What this project is

QPath measures what a user knows (an 18-question diagnostic), reads the live quantum
job market and recent research (SerpApi **Google Jobs** and **Google Scholar**), recommends career
paths with **deterministic scoring**, and then keeps tracking matched job opportunities for the
path the user chose. All market/research data comes from SerpApi; Google Gemini is used only for
structured extraction and grounded explanations, never for numbers or rankings.

**Core promise:** every number and ranking is computed by transparent, pure functions with named
constants; AI output is schema-validated, grounded in supplied evidence, and always labelled
("AI-generated from the data shown" vs "Template fallback (deterministic)").

---

## 2. Key features (as built)

| Feature | Description |
|---|---|
| **Orientation diagnostic** | 18-question quiz (interests slider first, one question per screen, review before submit). Deterministic scoring: difficulty 1–3 worth 1–3 points, "Not sure" = 0, no negative marking. Results show a readiness radar (Recharts + accessible table) and per-concept feedback. |
| **Market Pulse** | Six subfield cards with active-posting counts, top skills, research themes, seniority/PhD mix, extraction-coverage caveat, trend sparklines (only when ≥ 2 daily snapshots exist). |
| **Six career paths** | Each path scored `0.40 × interest + 0.30 × demand + 0.30 × readiness` (log-compressed demand), ranked server-side, shown with score breakdown, evidence panel (posting counts, PhD share, top skills, sample postings) and an honest AI explanation. Declaring skills never changes path scores. |
| **Opportunity tracker** | Choose a path → feed of matched postings with match badge (`0.6 × skill overlap + 0.4 × readiness`; "Not enough info" when no extracted skills), NEW badge (posting first seen after last "Mark all as seen"), region/internship filters, refresh status pill. |
| **Method page** | Verbatim contents of `docs/DATA_AND_METHOD.md` plus live numbers (SerpApi calls per engine, posting totals, extraction coverage, last refresh times). |
| **Admin / call log** | Every SerpApi call (live or fixture) is logged in `serpapi_call_log`; admin endpoints (refresh, extraction) guarded by `X-Admin-Token`. |

---

## 3. Architecture

```
Browser (React / Vite / TypeScript)
        │  HTTP/JSON
        ▼
FastAPI  /api/v1          — thin routers: parse → call one service → return Pydantic schema
        ▼
services/                 — ALL business logic (pulse, quiz, scoring, paths, tracker,
                            match, extraction, research, ingestion, skills, explanation)
        ▼                       ▼
models/ (SQLAlchemy 2.x,  integrations/
 SQLite, WAL mode)          serpapi/client.py  (fixture or live, daily cap, call log)
                            gemini/client.py   (StructuredLLM Protocol, rate limit, retry)
                            └─ FakeStructuredLLM for tests (no network in tests)
```

- **Strict layering:** routers have zero business logic and zero DB queries; integrations are the
  only code allowed to touch SerpApi or Gemini.
- **Sync everywhere:** plain `def` endpoints, sync SQLAlchemy sessions, sync `httpx.Client`.
- **Config:** all env access goes through `backend/app/core/config.py` (pydantic-settings).
- **Errors:** domain exceptions (`NotFoundError`, `SerpApiError`, `SerpApiCapExceeded`,
  `LLMOutputError`, …) → central handlers → uniform JSON `{ "error": { code, message } }`.
- **Database:** SQLite with WAL enabled; `create_all` at startup; **no Alembic/migrations**
  (intentional, recorded in ARCHITECTURE.md). Idempotent seeding/upserts everywhere.
- **Scheduler:** APScheduler 3.x `BackgroundScheduler`, off by default (`SCHEDULER_ENABLED=false`);
  cron strings from env; each job opens its own DB session; failures land in `refresh_runs` with
  scrubbed error text.

### Repository layout

```
backend/     FastAPI app: core/ (config, logging, errors), db/, models/, schemas/,
             api/v1/ (thin routers), services/, integrations/ (serpapi, gemini),
             scheduler/, data/ (seeded JSON), tests/ (unit + integration + fixtures)
frontend/    Vite + React + TS: app/, pages/, features/ (pulse, diagnostic, paths,
             tracker, skills), components/ (ui, layout), lib/ (apiClient, format, profileId),
             types/api.ts (mirrors backend schemas)
docs/        BUILD_PLAN.md, ARCHITECTURE.md, DATA_AND_METHOD.md, DEMO_SCRIPT.md, M10_SPOTCHECK.csv
scripts/     record_fixtures.py (live recording), seed_demo_history.py, m10_spotcheck.py
```

---

## 4. Tech stack (approved, nothing beyond it)

**Backend:** Python 3.12, FastAPI, Uvicorn, Pydantic v2 + pydantic-settings, SQLAlchemy 2.x
(2.0 style), SQLite, httpx (sync), `google-genai` (never the deprecated `google-generativeai`),
APScheduler 3.x, pytest / pytest-cov, ruff.

**Frontend:** Node LTS, Vite, React, TypeScript (strict, no `any`), React Router, TanStack Query,
Tailwind CSS, Recharts, Vitest + React Testing Library, ESLint, Prettier.

---

## 5. Data sources & method

- **Google Jobs via SerpApi:** one *core* search per subfield (feeds headline counts and demand)
  plus up to three *extended* searches (excluded from headline counts so query-count imbalance
  cannot distort comparative demand). Postings de-duplicated by title, company, location.
- **Google Scholar via SerpApi:** one date-sorted search per subfield (~20 recent papers) for
  qualitative research themes only. Scholar `total_results` is **never** used (erratic: same query
  returned 5,250 vs 5,040 on two runs) — a regression test enforces this.
- **Data as of:** live capture 10 Oct 2026 (38 Google Jobs + 12 Scholar live calls during
  development); 249 postings stored, including 4 Oct fixture-captured postings.
- **Formulas:**
  - Demand: `ln(1 + active) / ln(1 + largest active) × 100` (log scale).
  - Path score: `0.40 × interest + 0.30 × demand + 0.30 × readiness` (named constants; weights are
    a judgement, not fitted).
  - Opportunity match: `0.6 × skill overlap + 0.4 × readiness`, only when both sides have skills.
  - Readiness: `100 × earned / available` per subfield (difficulty-weighted).

---

## 6. AI (Gemini) usage

One LLM (`google-genai` structured output), three jobs, all through `integrations/gemini/` behind a
`StructuredLLM` Protocol with a `FakeStructuredLLM` for tests:

1. **Skill extraction** — reads first ~3,000 chars per posting, picks from a fixed 53-skill
   vocabulary plus seniority / PhD / internship flags. Batched (5 postings per call), results
   persisted so each posting is extracted once. Flag derivation is post-Phase-5 **evidence-based**
   (seniority only when the claimed bucket's keyword appears in title/description; `requires_phd`
   fully text-derived; internship from title/extensions only) after an M-10 spot check found model
   flags wrong in 15/20 sampled postings.
2. **Research themes** — 3–5 themes grounded strictly in supplied Scholar titles/snippets.
3. **Path explanations** — one batched call for all 6 paths; every number in the output is
   validated against the evidence JSON, hallucinated numbers ⇒ deterministic template fallback.
   Gemini quota exhaustion degrades to templates with zero UI failures.

Prompts live as named constants and always state: use only supplied data, never invent
numbers/URLs, return null when unknown. The LLM never produces a score or ranking.

---

## 7. SerpApi rules of the road

- All traffic via `integrations/serpapi/client.py` using REST `https://serpapi.com/search.json`
  (httpx; no SDK). Key passed as a query param only — never logged, never stored, never in fixtures.
- `SERPAPI_USE_FIXTURES=true` (default) reads recorded real responses in
  `backend/tests/fixtures/serpapi/`; `false` calls live, limited by `SERPAPI_DAILY_CALL_CAP`
  (UTC-day count from the call log) with `SerpApiCapExceeded` beyond it.
- Every call logged to `serpapi_call_log` (engine, query, source live/fixture, status). Responses
  with an `error` body raise `SerpApiError` — except "hasn't returned any results", treated as a
  valid empty result. Timeouts 30 s; one retry on timeout/5xx, never on 4xx. Google Jobs pagination
  uses `serpapi_pagination.next_page_token` only; `location` and `uule` are mutually exclusive.

---

## 8. Security & privacy

- CORS limited to `CORS_ORIGINS`; admin endpoints require `X-Admin-Token` compared with
  `secrets.compare_digest`.
- `GET /quiz` never exposes correct answers (schema structurally omits `correct_index`, test-asserted);
  scoring happens server-side.
- Only anonymous profile UUIDs and the user's own answers are stored. No secrets in source; fixtures
  are scrubbed of `api_key`.
- Frontend dev-only admin token typed in UI and kept in `sessionStorage`.

---

## 9. Testing

- **Backend pytest:** unit tests for pure logic (parsers, scoring, flag rules, match service);
  integration tests for endpoints/services against a **temporary SQLite DB** (never a mocked DB).
  SerpApi tests use recorded fixtures or `httpx.MockTransport`; Gemini tests use `FakeStructuredLLM`.
  No network in tests.
- **Frontend Vitest + React Testing Library** for logic-bearing components and key flows.
- Regression test asserting no fixture contains an API-key pattern. Every bug fix adds a regression
  test. Test names: `test_<unit>_<behavior>`.

---

## 10. Environment variables

Backend (`backend/.env`, copy from `backend/.env.example` — the `.env` itself is never committed):

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Shown in `/health` |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `DATABASE_URL` | `sqlite:///./data/pathfinder.db` | SQLite path |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed origins |
| `ADMIN_TOKEN` | `change-me` | Admin endpoints (`X-Admin-Token`) |
| `SERPAPI_API_KEY` | *(empty)* | Only needed in live mode |
| `SERPAPI_USE_FIXTURES` | `true` | Offline fixture mode |
| `SERPAPI_DAILY_CALL_CAP` | `60` | Live calls per UTC day |
| `SERPAPI_JOBS_MAX_PAGES` | `3` | Max pages per query (bootstrap) |
| `GEMINI_API_KEY` | *(empty)* | Extraction / themes / explanations |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model id |
| `GEMINI_REQUESTS_PER_MINUTE` | `5` | Client-side rate limit |
| `SCHEDULER_ENABLED` | `false` | APScheduler background refresh |
| `JOBS_DAILY_CRON` / `JOBS_INDIA_WEEKLY_CRON` / `SCHOLAR_WEEKLY_CRON` | `0 3 * * *` / `0 4 * * 1` / `0 5 * * 1` | Cron schedules |
| `ALLOW_UNVERIFIED_QUESTIONS` | `true` | Serve quiz questions pending verification |
| `DEMO_MODE` | `false` | Serve labelled demo history |

Frontend (`frontend/.env`): `VITE_API_BASE_URL` (default `http://localhost:8000/api/v1`).

---

## 11. Quick start & development commands

```bash
git clone https://github.com/aprajitsinha29-creator/Qpath.git
cd Qpath
python setup_project.py          # one-time setup

# edit backend/.env and frontend/.env (copy the .env.example files)
python setup_project.py --start  # then run a refresh via admin (default token: change-me)
# open http://localhost:5173
```

```bash
make setup         # one-time setup
make dev-backend   # uvicorn (backend)
make dev-frontend  # vite (frontend)
make test          # backend pytest + frontend vitest (offline, fixture mode)
make lint          # ruff + eslint + prettier
make format
make record-fixtures  # one-off live SerpApi recording (uses credits)
```

Fixture mode runs the whole app and test suite with **no API keys**. Gemini-backed features need
`GEMINI_API_KEY`; without it they fall back to labelled templates or empty states.

---

## 12. Status

| Phase | Description | Status |
|---|---|---|
| 0 | Foundation: FastAPI backend, health endpoint, SerpApi client (fixture mode), frontend shell | ✅ Done |
| 1 | Market Pulse: six subfield cards, active-posting counts, de-duplication | ✅ Done |
| 2 | Intelligence layer: Gemini skill extraction + Scholar research themes, pulse detail pages | ✅ Done |
| 3 | Orientation diagnostic: 18-question quiz, readiness scoring, per-concept feedback | ✅ Done |
| 4 | Path matcher: deterministic ranked paths, grounded explanations, declared-skills picker (carry-over on branch `skillp`) | ✅ Done |
| 5 | Opportunity tracker: chosen path, seen state, feed with match scores, NEW badges, sparklines, refresh status, scheduler | ✅ Done |
| 6 | Not built | — |
| 7 | Submission hardening / demo | — Not built |

Post-Phase-5 follow-up (M-10): evidence-based flag-derivation fix in `services/flag_rules.py`
after the extraction spot check (residuals honestly documented — not re-measured after the fix).

---

## 13. Known limits (honesty first)

- Posting counts are a **sample, not a census**: page-capped Google Jobs ingestion; busy subfields
  get flagged as saturated. A "low data" badge shows when active postings < 8.
- **India view is thin and indicative only.**
- Duplicates (same job in several locations) and non-quantum leakage (company names containing
  "quantum", e.g. QuantumBlack; faculty/policy/assembly roles) inflate counts slightly.
- **Quiz answers are unverified beyond their drafting:** LLM-assisted drafting, one-by-one author
  review, cross-check by answering in a second model (DeepSeek — all 18 matched). No external expert
  review; questions remain `verified=false` pending owner sign-off (M-08).
- Skill extraction tends to add skills rather than miss them; coverage caveats are shown per subfield.
- Free-tier Gemini quotas are small → explanations may fall back to templates.
- No Alembic: schema changes require dropping/recreating the DB. Scheduler off by default; demo
  refreshes run manually.
- The app is a **decision aid** — it makes no claim about hiring odds or salary.

---

## 14. AI tools used in development

- **Google Gemini** (in-app, as described above). **DeepSeek** — once, as a quiz-key cross-check.
- **Codebuff (GLM LLM coding agent)** assisted with code, tests and documentation; all behavioural
  logic is reviewed and owned by the author.
- **SerpApi Google Jobs + Google Scholar** supplied all market and research data; no other dataset.

---

## 15. Documentation map

| File | Contents |
|---|---|
| `AGENTS.md` | Engineering standards and agent rules (this project's "constitution") |
| `README.md` | Setup, architecture summary, SerpApi usage, limits |
| `docs/BUILD_PLAN.md` | The phased build plan |
| `docs/ARCHITECTURE.md` | Layer diagram, data flows, per-phase decision log, known limits |
| `docs/DATA_AND_METHOD.md` | Sources, formulas, accuracy checks, honest limits (rendered on the Method page) |
| `docs/DEMO_SCRIPT.md` | 3-minute demo shot list |
| `docs/M10_SPOTCHECK.csv` | Extraction spot-check data |
