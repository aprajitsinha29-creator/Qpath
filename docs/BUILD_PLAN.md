# QPath — Build Plan & Project Context

> Working name: **QPath** (formerly "Quantum Pathfinder"; renamed 2026-10-12). Created 2026-10-03 for the SerpApi India Hackathon 2026.
> This file is **self-contained**: a new chat or a new coding agent needs nothing else to understand the project, the decisions behind it, or how to build it.

---

## Table of contents

0. How to use this document
1. Project context (what, why, decisions, verified facts)
2. Manual tasks (everything only YOU can do)
3. Engineering standards for AI coding agents (copy into `AGENTS.md`)
4. Technical reference (architecture, env, data model, endpoints, formulas, prompts, vocabulary, taxonomy)
5. Build phases 0–7 (each ends with a working, testable product)
6. Quiz question verification method
7. Submission checklist
8. Risks and fallbacks

---

## 0. How to use this document

### 0.1 Resuming in a new chat

Upload this file and say: *"This is my project context and build plan. Read Section 1 fully, then help me with <task>. Keep the ruthless-mentor tone: challenge weak points, verify claims with sources."* Nothing else needs re-explaining.

### 0.2 Building a phase with a coding agent

For **every** phase, in this order:

1. Do the **manual prerequisites** listed at the top of the phase (see also Section 2).
2. Start a **fresh agent session** in the repo root.
3. Paste the kickoff prompt below (replace `N`).
4. Let the agent finish **only that phase**. Do not let it start the next one.
5. Run the phase's **acceptance checks** yourself (exact commands are listed).
6. Commit, tag `phase-N`, and only then move on.

**Kickoff prompt template**

```text
Read AGENTS.md fully, then docs/BUILD_PLAN.md Sections 1, 4 and Phase N.
Implement Phase N ONLY. Follow the steps in order. Before writing code, list the
files you will create or modify. After each numbered step group: run lint and tests,
then commit with a Conventional Commit message. At the end run every acceptance
check, paste the outputs, update docs/ARCHITECTURE.md, and report: deviations,
assumptions, anything you were unsure about. Do not add dependencies that are not in
the approved stack without asking. If a real SerpApi response differs from what this
plan assumes, inspect the fixture and adapt the parser defensively; report it.
```

### 0.3 Which tool does what

| Tool | Use for |
|---|---|
| **Freebuff CLI** (primary) | Whole-phase builds using the kickoff prompt |
| **Antigravity CLI** | Debugging and precise, complex fixes (use the debug protocol in Section 3.13) |
| **GitHub Copilot** (fallback) | Small edits when the others are unavailable |

Instruction files: Freebuff reads `AGENTS.md` and `knowledge.md`; Copilot reads `.github/copilot-instructions.md`. The plan creates all three (the latter two are one-line pointers to `AGENTS.md`). If Antigravity does not pick up `AGENTS.md` automatically, paste Section 3 into its context at session start.

### 0.4 Phase map

| Phase | Name | What you can do at the end |
|---|---|---|
| 0 | Foundation | Run backend + frontend, see health status, fixtures recorded |
| 1 | Market Pulse v1 | See live (or fixture) quantum job volume per subfield |
| 2 | Intelligence layer | See AI-extracted top skills and research themes per subfield |
| 3 | Orientation diagnostic | Take the quiz, see a readiness radar |
| 4 | Path matcher | Get ranked career paths grounded in live data — **first submittable build** |
| 5 | Opportunity tracker | Track a path, see new postings with match scores, scheduler running |
| 6 | Gap analysis & learning path | Get a ranked skill-gap list and an ordered learning plan |
| 7 | Submission hardening | Judge-ready repo, Method page, README, demo script |

**Cut line:** Phase 4 is the earliest build worth submitting. Phase 5 is strongly recommended (continuous tracking was an explicit goal). Phase 7 is mandatory before submitting; if time is short, do Phase 7 right after Phase 4 or 5 and skip Phase 6.

**Deadline:** October 10, 2026, 23:59 IST (confirmed on the hackathon site).

---

## 1. Project context

### 1.1 Builder and situation

- Builder: Aprajit, first-year B.Tech CSE (AI & ML) student. Also building **Ananta Quantum Studio** (a browser-based quantum education/research platform). QPath is a **separate, standalone project** born from one planned Ananta feature.
- Uses coding agents heavily ("vibe coding"). Stack chosen: **FastAPI + React**, **Gemini API** (no Claude API keys available), SerpApi keys already obtained.
- Working style requested: ruthless mentor. Challenge ideas, check the market before building, cite sources, say when unsure.

### 1.2 The hackathon (verified from the official site on 2026-10-03)

- **SerpApi India Hackathon 2026.** Submit by **Oct 10, 2026 at 23:59 IST**. Open to India residents 18+. Solo or teams of up to five.
- **Judging (unweighted, considered together):** idea strength, originality, technical complexity, usefulness, **meaningful SerpApi usage** ("does the project depend on search data to deliver useful functionality?"). Judges include SerpApi developer advocates.
- **Submission requires:** public GitHub repo with setup instructions; **demo video under 3 minutes showing the project running locally**; project description (what, who it helps, how SerpApi is used); one track; disclosure of whether the project pre-existed; list of AI tools used; accept Rules + Terms. Test repo and video links in a private/incognito window.
- **Rules that bite:**
  - SerpApi must make a *material* contribution; an isolated or cosmetic call is insufficient.
  - **Exposing API keys or personal data in public materials can disqualify.**
  - **Judges may review repository history** → commit incrementally with meaningful messages; no single giant commit.
  - "Abuse of SerpApi services" is a disqualification ground. See manual task M-16 about credits.
  - Each account may hold up to 3 active projects.
- **Free resources:** a free SerpApi account has 250 search credits/month; every valid submission later receives 1,000 credits.
- **Track to select:** **Knowledge & Public Interest** (its listed tags include Scholar, Jobs, News, Accessibility; it covers education, research, jobs). Open Innovation is the fallback.

### 1.3 Product definition

**One-line pitch:** a live-data career navigator for quantum computing. It measures what you know, shows where the quantum job market and research are moving, recommends the career paths that fit you, and keeps tracking opportunities for the path you choose.

**User journey**

1. **Market Pulse** (landing, no sign-in): one card per subfield with live posting volume (Google Jobs), most-demanded skills (Gemini-extracted), new postings, and a "research focus" strip (Scholar → Gemini themes). A "SerpApi activity" panel makes the API's role visible.
2. **Orientation diagnostic:** 6 interest sliders + 18 verified multiple-choice questions (3 per subfield, with a "Not sure" option). Output: readiness (0–100) and interest per subfield.
3. **Path matcher:** six career paths scored by *deterministic code* from interest, readiness and live demand. Gemini only writes the explanation, grounded in the supplied numbers.
4. **Opportunity tracker:** user tracks a path; sees jobs/internships with match scores and "new since your last visit" badges; a scheduler keeps data fresh.
5. **Gap analysis & learning path:** demanded skills the user lacks, ranked; an ordered concept plan respecting prerequisites; user marks concepts complete.

**Design principles (why it is not "a wrapper")**

- Scoring and ranking are deterministic, tested code. The LLM extracts structure and writes explanations; it never produces numbers.
- Every AI output is validated against a schema and a controlled vocabulary.
- The app is honest about its data: sampled counts, qualitative research themes, accuracy of AI extraction measured and reported.

### 1.4 Ideas that were evaluated and rejected (do not re-propose)

| Idea | Why it died |
|---|---|
| Job-application auto-apply pipeline | Job boards block automation; SerpApi only helps with discovery |
| LinkedIn content/trend suggester | LinkedIn blocks scrapers; the "trends + LLM → posts" pattern is a commodity (SaaS tools, $4 no-code templates, agent skills) |
| Generic job-market intelligence dashboard | Hackathon cliché on lablab.ai; GetJobPulse India already live (weekly analysis of thousands of AI/DS listings); AureliusTalent does skill-gap roadmaps |
| Competitor/price intelligence | Funded SaaS category (Prowl, Competely, Price Sentinel at ~$13k MRR, and more) |

**Closest competitor to the chosen idea:** *qubitsok.com* — a live quantum jobs + research-papers aggregator/newsletter (crawls ~20 sources weekly, classifies with NLP; ~780 job and ~540 paper subscribers at the time checked). It is a **passive aggregator**. QPath differs by **connecting live signal to a personalized decision**: diagnostic → ranked paths → gap analysis → tracked opportunities. Do **not** drift into "a list of jobs" or "a list of papers" without a decision layer; that shape is already owned.

### 1.5 Verified facts about SerpApi data (probe run on 2026-10-02)

**Google Jobs** (`engine=google_jobs`)
- Query "quantum computing", `location=India`, `gl=in`: **10 postings on page 1**, `next_page_token` present, description length ≈ 2,500 chars on the first posting. Global (no location): 10 postings, description ≈ 7,200 chars.
- Keys seen on a posting: `title, company_name, location, via, share_link, thumbnail, extensions, source_link, job_title, description, apply_options, job_id`. **`job_highlights` appeared in the global result but not the India one** → treat **every field except title/company as optional**.
- Docs: pagination is via `serpapi_pagination.next_page_token`; the old `start` offset is discontinued; `location` and `uule` cannot be combined.
- Quantum jobs in India are limited in volume; global results are richer. The UI offers an India/Global toggle.

**Google Scholar** (`engine=google_scholar`)
- `search_information.total_results` for `"quantum error correction"` by single year: 2021 → 413, 2022 → 979, 2023 → 666, 2024 → 5,250, 2025 → 1,770; re-running 2024 with `no_cache` gave 5,040. **Erratic → NOT usable as a trend/growth metric.** Never compute "papers up X%" from it.
- Usable instead: `scisbd=1` ("articles added in the last year, sorted by date") with `num` (≤ 20 per page; verify), and `organic_results[]` fields `title, snippet, link, publication_info.summary, inline_links.cited_by.total`. The project uses Scholar for **qualitative research themes from recent papers**, not counts. (Citation counts are not used for "what's current" — new papers have almost no citations.)

### 1.6 Gemini facts and uncertainty

- Use the **`google-genai`** SDK (`from google import genai`); it replaced the deprecated `google-generativeai`.
- Structured output: pass `response_mime_type="application/json"` together with a `response_schema` (Pydantic model).
- Model names and free-tier limits change often and secondary sources disagree (mentions of `gemini-2.5-flash` and a `gemini-3.5-flash` launched in May 2026; free-tier numbers vary). Therefore: **never hardcode a model name or limit** — read `GEMINI_MODEL` and `GEMINI_REQUESTS_PER_MINUTE` from env, and confirm the current values in Google AI Studio (manual task M-04).

### 1.7 Quantum market evidence (secondary, treat with suspicion)

From a March 2026 qubitsok.com analysis of ~1,212 job postings and ~15k papers: error correction was the most-tagged area (~183 tags), then superconducting circuits (~135), FPGA/decoder engineering (~109), neutral atoms (~88), quantum ML (~84); NISQ-style algorithms and quantum annealing were declining. Other guides expect fault-tolerance-era demand (QEC, compilers, hybrid quantum-classical/HPC) to outpace pure algorithm theory. Cryptography/networking showed **no verified hiring-volume evidence** (much of it is classical post-quantum security work).

**Caveats:** sources are commercial/content-marketing; tag counts are not hiring difficulty; estimates of QEC specialist headcount disagree widely. The project's own SerpApi data is meant to confirm or contradict these claims, and the UI must report the result honestly — including "low data" for thin subfields.

### 1.8 Relationship to Ananta Quantum Studio

- Submit QPath as its **own repo**, README and demo. Do **not** demo Ananta (it would dilute the "SerpApi is essential" story). Mention Ananta as related work only; disclose truthfully that QPath is a new project that shares design ideas (the taxonomy) with Ananta.
- Later integration: the diagnostic can be replaced by Ananta's mastery graph; the taxonomy in `taxonomy.json` is designed to become that schema. Do not build any Ananta integration now.

### 1.9 Non-goals (do not build)

Auto-applying to jobs; scraping LinkedIn; login/auth; payments; email digests; adaptive quizzing; per-user SerpApi tracking; Docker/CI/migrations; generic job board or paper feed with no decision layer; any Ananta coupling.

---

## 2. Manual tasks

These are the things only you can do. IDs are referenced inside phases so you can finish them **before** delegating a phase.

| ID | Task | Needed before | How |
|---|---|---|---|
| M-01 | Verify toolchain | Phase 0 | `python3 --version` (3.12 ✔ seen), `node -v` (need current LTS, 20+; install via `nvm` if missing), `git --version`, `make --version`. Remember: system `pip install` is blocked on your Ubuntu — the Makefile uses a venv at `backend/.venv`. |
| M-02 | Create the GitHub repo | Phase 0 | Name e.g. `quantum-pathfinder`. Keep it **private** until M-13 is done, then make it public. Add a LICENSE of your choice (MIT is typical). |
| M-03 | Put the SerpApi key in `backend/.env` | Phase 0 (step 0.5 live recording) | Copy `backend/.env.example` → `backend/.env`, set `SERPAPI_API_KEY`. **Never paste keys into an agent chat or commit them.** |
| M-04 | Get a Gemini API key and choose the model | Phase 2 | Create a key in Google AI Studio → `GEMINI_API_KEY`. Check which models your key can use and the free-tier request limits shown there; set `GEMINI_MODEL` and `GEMINI_REQUESTS_PER_MINUTE` accordingly (keep the latter conservative). |
| M-05 | Install/log in to the coding tools | Phase 0 | Freebuff CLI, Antigravity CLI, Copilot. In the repo root run Freebuff once and confirm it reads `AGENTS.md` (ask it "what are the 3 commit rules?"). |
| M-06 | Record SerpApi fixtures | After Phase 0 code, before Phase 1 | Run `make record-fixtures` once (≈17–20 credits). Open 2–3 fixture files and confirm they contain real postings/papers and **no API key**. Commit them. |
| M-07 | Review `taxonomy.json`, `career_paths.json`, search query plan | Before Phase 1 | Read Section 4.6/4.9; edit wording or queries you disagree with. These drive everything downstream. |
| M-08 | **Author and verify the quiz bank (blocker for Phase 3)** | Before Phase 3 completes | Follow Section 6 exactly. 18 questions; only questions you mark `"verified": true` are served in the final build. Start this **now, in parallel with Phase 0–2**. |
| M-09 | Review `skills_vocab.json` | Before Phase 2 | Check canonical names/aliases; add skills you know are common in quantum job ads. The AI can only output ids from this list. |
| M-10 | Spot-check AI skill extraction | End of Phase 2 | Pick 20 random postings; compare the extracted skills/seniority/PhD flag with the posting text. Record accuracy (target ≥ 80%). Report the number on the Method page (Phase 7). |
| M-11 | Review skill→concept mapping; curate a few resource links | Phase 6 | Approve the agent's proposed mapping. Optionally hand-pick 1–2 good public resources per top concept for `resources.json`. Do not let AI invent URLs. |
| M-12 | Decide scheduler policy | Phase 5 | Keep `SCHEDULER_ENABLED=false` while developing. Enable only for the final days or when demoing continuous tracking. |
| M-13 | Secret scan before going public | Phase 7 | Search history and tree for keys (`git log -p \| grep -i -E "api_key\|AIza\|serpapi"` or run `gitleaks`/`trufflehog`). If anything leaked: **rotate the key**, rewrite history or recreate the repo. |
| M-14 | Record the demo video | Phase 7 | < 3 min, screen recording of the project **running locally**. Upload as unlisted; open in a private window to test. |
| M-15 | Complete the submission form | Phase 7 | Track: Knowledge & Public Interest. Describe SerpApi usage (see Section 7). Pre-existing project? → new project; mention it shares ideas with Ananta. List AI tools: Freebuff, Antigravity CLI, GitHub Copilot, Claude (planning/consultation), and Gemini (runtime feature in the app). |
| M-16 | Credits policy | Before you run out | Use fixtures during development and keep the daily call cap. If you need more credits, **ask the organizers** (hackathon contact is listed on the hackathon site) rather than relying on multiple free accounts — the rules list "abuse of SerpApi services" as a disqualification ground and I could not confirm that multiple free accounts are allowed. |

---

## 3. Engineering standards for AI coding agents

> **Copy this entire section, verbatim, into `AGENTS.md` at the repo root** (Phase 0 step 0.1 does this). Everything here is a rule, not a suggestion.

### 3.1 Repository structure

```text
quantum-pathfinder/
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

---

## 4. Technical reference

### 4.1 Architecture

```text
 React (Vite) ──HTTP/JSON──▶ FastAPI /api/v1
                                │
              routers (thin) ───┤
                                ▼
                            services  ◀── pure scoring / gap / plan functions
                           │        │
                           ▼        ▼
                       models   integrations
                       (SQLite)   ├─ serpapi/client ──▶ serpapi.com (Google Jobs, Google Scholar)
                           ▲      │     └─ fixtures (offline mode) + call log + daily cap
                           │      └─ gemini/client  ──▶ Gemini API (structured JSON only)
                           │
                       scheduler (APScheduler, optional) ──▶ ingestion + extraction services
```

**SerpApi engines used:** `google_jobs` (core: market pulse, skills, feed, tracking) and `google_scholar` (research themes by subfield).

### 4.2 Environment variables

`backend/.env.example` (commit this; real values go in `backend/.env`):

```bash
APP_ENV=development
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./data/pathfinder.db
CORS_ORIGINS=http://localhost:5173
ADMIN_TOKEN=change-me

SERPAPI_API_KEY=
SERPAPI_USE_FIXTURES=true          # true = read recorded JSON, spend no credits
SERPAPI_DAILY_CALL_CAP=60          # hard stop for live calls per UTC day
SERPAPI_JOBS_MAX_PAGES=3           # bootstrap depth only; daily runs use 1 page

GEMINI_API_KEY=
GEMINI_MODEL=                      # set to a model available to your key (see AI Studio)
GEMINI_REQUESTS_PER_MINUTE=10      # keep below your tier's limit

SCHEDULER_ENABLED=false
JOBS_DAILY_CRON=0 3 * * *          # daily core global refresh
JOBS_INDIA_WEEKLY_CRON=0 4 * * 1   # weekly India refresh
SCHOLAR_WEEKLY_CRON=0 5 * * 1      # weekly Scholar + themes

ALLOW_UNVERIFIED_QUESTIONS=false   # true only while building the UI
DEMO_MODE=false                    # Phase 7: serve labeled demo history
```

`frontend/.env.example`:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

`Settings` must **fail fast** at startup if `SERPAPI_USE_FIXTURES=false` and `SERPAPI_API_KEY` is empty, or if a Gemini feature is invoked without `GEMINI_API_KEY`/`GEMINI_MODEL` (raise a clear error; do not crash the whole app at import time for Gemini).

### 4.3 Data model (SQLAlchemy tables)

| Table | Key columns | Notes |
|---|---|---|
| `subfields` | `id` (str PK), `name`, `description`, `sort_order`, `is_scored` | Seeded from `taxonomy.json`. `foundations` is a pseudo-subfield with `is_scored=false` |
| `concepts` | `id` (str PK), `subfield_id` (FK), `name`, `description`, `prerequisites` (JSON list of concept ids) | Seeded |
| `skills` | `id` (str PK), `name`, `aliases` (JSON), `subfield_ids` (JSON), `concept_ids` (JSON, may be empty until Phase 6) | Seeded from `skills_vocab.json` |
| `career_paths` | `id`, `title`, `subfield_id`, `description`, `typical_titles` (JSON) | Seeded; one path per scored subfield |
| `questions` | `id`, `subfield_id`, `concept_id`, `difficulty` (1–3), `stem`, `options` (JSON, exactly 4), `correct_index`, `explanation`, `source_refs` (JSON), `verified` (bool), `sort_order` | Seeded from `quiz_questions.json` |
| `job_postings` | `id`, `dedupe_key` (**unique**), `serp_job_id`, `title`, `company`, `location`, `via`, `description`, `apply_url`, `extensions` (JSON), `is_internship`, `seniority` (nullable), `requires_phd` (nullable bool), `extraction_status` (`pending`/`done`/`failed`), `extraction_attempts`, `first_seen_at`, `last_seen_at`, `is_active` | `dedupe_key` = sha1 of normalized `title+company+location` (SerpApi `job_id` may change between fetches) |
| `job_posting_subfields` | `posting_id`, `subfield_id`, `region` (`global`/`india`), `tier` (`core`/`extended`), `source_query`, `first_seen_at`, `last_seen_at` | Subfield tag comes from the query that found it, plus the model's `primary_subfield_id`. If a posting is found by both tiers for the same subfield, keep "core". |
| `job_posting_skills` | `posting_id`, `skill_id` | Only vocabulary ids |
| `paper_snapshots` | `id`, `subfield_id`, `batch_id`, `query`, `title`, `snippet`, `link`, `publication_summary`, `year` (nullable), `cited_by` (nullable), `fetched_at` | One batch per refresh |
| `research_themes` | `id`, `subfield_id`, `batch_id`, `themes` (JSON: `[{label, summary, paper_ids}]`), `generated_at`, `model` | |
| `pulse_snapshots` | `id`, `subfield_id`, `snapshot_date`, `region`, `active_postings`, `new_postings`, `internship_postings` | Unique on (subfield, date, region); powers trend lines |
| `refresh_runs` | `id`, `kind` (`jobs`/`scholar`/`extraction`), `mode`, `started_at`, `finished_at`, `status`, `serpapi_calls`, `details` (JSON), `error` | |
| `serpapi_call_log` | `id`, `engine`, `query`, `source` (`live`/`fixture`), `status`, `created_at` | Drives the daily cap and the activity panel |
| `profiles` | `id` (UUID str), `created_at`, `last_seen_at`, `interests` (JSON `{subfield_id: 1–5}`), `declared_skills` (JSON), `chosen_path_id` (nullable), `completed_concepts` (JSON) | Anonymous; no personal data |
| `assessments` | `id`, `profile_id`, `taken_at`, `answers` (JSON), `scores` (JSON `{subfield_id: 0–100}`) | History kept; latest is used |
| `path_explanations` | `id`, `profile_id`, `assessment_id`, `path_id`, `evidence_hash`, `payload` (JSON), `generated_by` (`llm`/`template`), `model`, `generated_at` | Cache keyed by evidence hash |

### 4.4 API surface (prefix `/api/v1`)

| Method & path | Phase | Purpose |
|---|---|---|
| `GET /health` | 0 | `{status, version, env, db}` |
| `GET /taxonomy` | 1 | Subfields + concepts + career paths |
| `GET /pulse?region=` | 1 | Six pulse cards |
| `GET /pulse/{subfield_id}` | 2 | Card detail: skills, themes, mix |
| `GET /pulse/{subfield_id}/postings?region=&internship=&limit=&offset=` | 1 | Posting list |
| `GET /pulse/{subfield_id}/trend` | 5 | Snapshot series |
| `GET /meta/serpapi-activity` | 1 | Today's calls, cap, last 20 calls |
| `GET /meta/refresh-status` | 5 | Last runs per kind |
| `GET /meta/method` | 7 | Data & method facts for the Method page |
| `POST /admin/refresh/jobs` | 1 | `{mode: bootstrap\|daily, subfield_id?, region}` (admin token) |
| `POST /admin/extract?limit=` | 2 | Run Gemini extraction on pending postings |
| `POST /admin/refresh/scholar` | 2 | Fetch papers + generate themes |
| `GET /quiz` | 3 | Questions **without** answers |
| `POST /profiles` | 3 | Create anonymous profile |
| `GET /profiles/{id}` | 3 | Profile |
| `POST /profiles/{id}/assessment` | 3 | Submit interests + answers → scores + feedback |
| `GET /profiles/{id}/paths` | 4 | Ranked paths with evidence |
| `POST /profiles/{id}/paths/{path_id}/explanation` | 4 | Grounded explanation (cached) |
| `PUT /profiles/{id}/skills` | 4 | Declared skills |
| `PUT /profiles/{id}/chosen-path` | 5 | Track a path |
| `GET /profiles/{id}/opportunities?internship=&region=&limit=&offset=` | 5 | Matched postings + `is_new` flags |
| `POST /profiles/{id}/seen` | 5 | Update `last_seen_at` |
| `GET /profiles/{id}/gap-analysis` | 6 | Ranked skill gaps |
| `GET /profiles/{id}/plan` | 6 | Ordered concept plan |
| `PUT /profiles/{id}/plan/concepts/{concept_id}` | 6 | Mark complete/incomplete |

Error shape for every failure: `{"error": {"code": "<snake_case>", "message": "<human readable>"}}`.

### 4.5 Scoring and ranking formulas (constants live in `services/scoring_service.py`)

**Quiz score per subfield** — each question has `difficulty` 1–3 used as points. A correct answer earns its points; wrong or "Not sure" earns 0 (no negative marking; "Not sure" exists so guessing does not inflate scores).
`readiness_s = 100 × (points earned in s) / (points available in s)` → with difficulties 1,2,3 the total is 6.

**Normalizations**
- `interest_n = (slider − 1) / 4` for slider 1–5.
- `readiness_n = readiness_s / 100`.
- `demand_n(s) = ln(1 + active_s) / ln(1 + max_active)`; `0` if `max_active = 0`. (Log scale stops one big subfield from flattening the rest.) `active_s` = number of active postings linked to subfield `s` through a CORE-tier query for the selected region. Unequal query counts across subfields would otherwise inflate demand for subfields with more queries.

**Path score** (paths map 1:1 to scored subfields)
`path_score = 100 × (W_INTEREST × interest_n + W_DEMAND × demand_n + W_READINESS × readiness_n)` with `W_INTEREST = 0.40`, `W_DEMAND = 0.30`, `W_READINESS = 0.30`.
Rationale: interest should lead (a beginner has low readiness everywhere), demand keeps recommendations grounded in the market, readiness favors a realistic start. Tie-break: higher demand, then alphabetical id.
**Low-data flag:** if `active_s < 8`, mark the path `low_data = true` and the UI states that demand evidence is thin.
**Saturation guard:** if ≥ 4 of 6 subfields hit the page cap during the latest bootstrap, add a note that demand differences are compressed by sampling.

**Posting match score** (Phase 5)
`skill_overlap = |posting_skills ∩ declared_skills| / max(1, |posting_skills|)`; `match = 100 × (0.6 × skill_overlap + 0.4 × readiness_n(primary subfield))`. If the posting has no extracted skills → `match = null` ("not enough information").

**Skill gap** (Phase 6) for the chosen path's subfield
`freq_k` = share of that subfield's active, extracted postings that mention skill `k`.
`proficiency_k = 1.0` if declared; else `0.5 × readiness_n(subfield of k)`; (if `k` has no subfield, `0`).
`gap_k = freq_k × (1 − proficiency_k)`. Rank descending; the top 8 feed the plan.

**Learning plan** (Phase 6): collect `concept_ids` of the top-gap skills, add all transitive prerequisites, drop completed concepts, topologically sort (Kahn's algorithm) with tie-break by summed gap weight (desc) then id. Prerequisite cycles are a data bug → a unit test over `taxonomy.json` must fail if any cycle exists.

### 4.6 Search query plan (`integrations/serpapi/queries.py`)

**Google Jobs** (`tier=core` runs in daily mode; `extended` only in bootstrap/manual full refresh):

| Subfield | Core query | Extended queries |
|---|---|---|
| `qec` | `quantum error correction` | `fault tolerant quantum computing` |
| `hardware` | `quantum hardware engineer` | `superconducting qubit`, `trapped ion quantum`, `neutral atom quantum` |
| `software` | `quantum software engineer` | `quantum compiler` |
| `algorithms` | `quantum algorithms` | `quantum applications scientist` |
| `qml` | `quantum machine learning` | — |
| `crypto_net` | `post-quantum cryptography` | `quantum key distribution`, `quantum networking` |

- **Demand fairness note on query counts:** The job query plan has unequal query counts per subfield (hardware 4, qml 1). To keep the demand signal fair, only postings found via a CORE-tier query count toward a subfield's headline and demand figures (postings linked only via extended queries still appear in posting lists).
- Global run: no location. India run: `location=India`, `gl=in`. All with `hl=en`.
- **Modes:** `bootstrap` = all queries, follow `next_page_token` up to `SERPAPI_JOBS_MAX_PAGES`; `daily` = core queries, 1 page. Each query's results are tagged with its subfield.
- Optional: SerpApi's Google Jobs API may support a recency `chips` filter (e.g. date posted). **Verify in the current docs before using; skip if unsupported.**
- **Credit math (for your planning):** daily global core = 6 calls/day; weekly India core = 6/week; weekly Scholar = 6/week. ≈ 180 + 24 + 24 ≈ 230 credits/month — near the 250 free limit, which is why the scheduler stays **off** during development and the call cap exists.

**Google Scholar** (one query per subfield, weekly): `scisbd=1`, `num=20`, `hl=en`.

| Subfield | Query |
|---|---|
| `qec` | `quantum error correction` |
| `hardware` | `quantum computing hardware qubits` |
| `software` | `quantum compiler transpilation` |
| `algorithms` | `quantum algorithms` |
| `qml` | `quantum machine learning` |
| `crypto_net` | `quantum key distribution OR post-quantum cryptography` |

**Fixture recording plan** (`scripts/record_fixtures.py`, ≈ 17–20 credits): 6 core global job queries (page 1); 1 query with page 2 via `next_page_token` (to test pagination); 2 India queries (`quantum error correction`, `quantum software engineer`); 6 Scholar queries (`scisbd=1`, `num=20`). Fixture file name = `<engine>__<slugified query>__<region/page>.json`. Refuses to overwrite existing files unless `--force`; scrubs any `api_key`.

### 4.7 Gemini prompts and schemas (`integrations/gemini/`)

**Skill extraction** (batch of ≤ 5 postings; descriptions truncated to ~3,000 chars)

```text
You extract structured data from quantum-industry job postings.
Rules:
- Use ONLY skill ids from the provided VOCABULARY. If a posting names a skill that is not in
  the vocabulary, put its plain-text name in unmapped_skills. Never invent ids.
- Do not guess. If the posting does not state seniority or a PhD requirement, return null/"unknown".
- primary_subfield_id must be one of the listed subfield ids, or null.
Return one item per input posting, in the same order, echoing posting_ref.
VOCABULARY: <skill id: name (aliases)> ...
SUBFIELDS: <id: name> ...
POSTINGS: <posting_ref, title, company, description> ...
```

```python
class PostingExtraction(BaseModel):
    posting_ref: str
    skill_ids: list[str]
    unmapped_skills: list[str]
    seniority: Literal["intern", "entry", "mid", "senior", "lead", "postdoc", "phd_student", "unknown"]
    requires_phd: bool | None
    is_internship: bool
    primary_subfield_id: str | None

class ExtractionBatch(BaseModel):
    items: list[PostingExtraction]
```

Post-validation: drop `skill_ids` not in vocabulary (move to `unmapped`), null out invalid `primary_subfield_id`, require `len(items) == len(inputs)` and matching `posting_ref`s; otherwise retry once, then mark each posting `failed` (attempts + 1; stop after 3 attempts). Rule-based internship detection (`\bintern(ship)?s?\b` in title/extensions) is OR-ed with the model's flag.

**Research themes** (per subfield; ≤ 20 papers as `[index] title — snippet`)

```text
Using ONLY the papers listed (titles and snippets), identify 3 to 5 distinct research themes.
For each: a label (max 6 words), a one-sentence summary (max 30 words), and the paper indexes
that support it. Do not use outside knowledge. Do not claim growth or trends; describe what
these recent papers are about.
```
Schema: `ThemeSet { themes: list[Theme{label, summary, paper_indexes: list[int]}] }`. Validate indexes are within range; drop themes with none.

**Path explanation** (grounded; input is a JSON blob of the numbers and evidence the backend computed)

```text
You write a short, honest career-fit explanation for one quantum career path.
Use ONLY the numbers and items in the provided JSON. Do not invent statistics, salaries,
company claims or URLs. If low_data is true, say that the demand evidence is thin.
Output: headline (max 12 words); reasons (exactly 3, each max 25 words, each tied to a
provided number); caveat (max 30 words); next_step (max 25 words).
```
If the call fails twice, return a **deterministic template** built from the same JSON and set `generated_by="template"` so the UI never breaks.

### 4.8 Starter skill vocabulary (`app/data/skills_vocab.json`)

Agent builds the JSON from this table (`id`, `name`, `aliases`, `subfield_ids`); `concept_ids` stays empty until Phase 6. **You review it in M-09.**

| id | name | aliases | subfields |
|---|---|---|---|
| python | Python | py | all |
| cpp | C++ | cplusplus | qec, hardware, software |
| rust | Rust | | software, qec |
| julia | Julia | | algorithms |
| qiskit | Qiskit | IBM Qiskit, qiskit sdk | software, algorithms, qml |
| cirq | Cirq | | software, algorithms |
| pennylane | PennyLane | | qml, algorithms |
| cuda_q | CUDA-Q | CUDA Quantum | software, algorithms |
| braket | Amazon Braket | AWS Braket | software |
| qsharp | Q# / Azure Quantum | Azure Quantum, QDK | software, algorithms |
| openqasm | OpenQASM | QASM | software |
| tket | TKET / pytket | pytket | software |
| stim | Stim | | qec |
| pymatching | PyMatching | MWPM | qec |
| circuit_compilation | Circuit compilation & transpilation | transpilation, qubit routing, circuit optimization | software |
| llvm_mlir | LLVM / MLIR | compiler infrastructure | software |
| hpc | HPC / parallel computing | MPI, Slurm, supercomputing | software, algorithms |
| gpu_programming | GPU programming | CUDA, GPU computing | software, algorithms |
| software_engineering | Software engineering practices | testing, CI/CD, version control | all |
| linear_algebra | Linear algebra | | all |
| quantum_mechanics | Quantum mechanics | | all |
| quantum_information | Quantum information theory | | all |
| probability_stats | Probability & statistics | | algorithms, qec, hardware |
| stabilizer_formalism | Stabilizer formalism | stabilizer codes | qec |
| surface_codes | Surface codes | topological codes | qec |
| ldpc_codes | qLDPC / LDPC codes | | qec |
| decoding_algorithms | Decoding algorithms | decoder, belief propagation, union-find | qec |
| noise_modeling | Noise modeling & characterization | randomized benchmarking, tomography | qec, hardware |
| error_mitigation | Error mitigation | ZNE, zero-noise extrapolation | software, algorithms |
| variational_algorithms | Variational algorithms | VQE, QAOA | algorithms, qml |
| quantum_simulation | Quantum simulation | Hamiltonian simulation | algorithms |
| quantum_chemistry | Quantum chemistry | molecular simulation | algorithms |
| optimization | Optimization | combinatorial optimization, operations research | algorithms |
| resource_estimation | Resource estimation | | algorithms, qec |
| tensor_networks | Tensor networks | | algorithms, qml |
| machine_learning | Machine learning | ML, deep learning | qml |
| pytorch | PyTorch | | qml |
| tensorflow | TensorFlow | | qml |
| superconducting_qubits | Superconducting qubits | transmon, circuit QED | hardware |
| trapped_ions | Trapped ions | ion trap | hardware |
| neutral_atoms | Neutral atoms | Rydberg arrays, optical tweezers | hardware |
| photonic_quantum | Photonic quantum computing | integrated photonics | hardware |
| cryogenics | Cryogenics | dilution refrigerator | hardware |
| microwave_rf | Microwave / RF engineering | RF | hardware |
| control_electronics | Control electronics & FPGAs | FPGA, Verilog, VHDL, RFSoC, real-time control | hardware, qec |
| optics_lasers | Optics & lasers | | hardware |
| pulse_control | Pulse-level control & calibration | calibration | hardware |
| nanofabrication | Nanofabrication | cleanroom | hardware |
| pqc | Post-quantum cryptography | PQC, lattice-based cryptography, ML-KEM, ML-DSA | crypto_net |
| qkd | Quantum key distribution | BB84 | crypto_net |
| applied_cryptography | Applied cryptography | | crypto_net |
| quantum_networking | Quantum networking | quantum repeaters, entanglement distribution | crypto_net |
| network_protocols | Network protocols | TCP/IP | crypto_net |

### 4.9 Taxonomy (`app/data/taxonomy.json`) and career paths (`career_paths.json`)

Subfield ids: `qec`, `hardware`, `software`, `algorithms`, `qml`, `crypto_net` (scored) and `foundations` (not scored; used only for prerequisites).

| Concept id | Name | Prerequisites |
|---|---|---|
| `found.linear_algebra` | Linear algebra for quantum | — |
| `found.qubits_and_gates` | Qubits, gates, circuits | found.linear_algebra |
| `found.measurement` | Measurement & probabilities | found.qubits_and_gates |
| `found.entanglement` | Entanglement | found.qubits_and_gates |
| `qec.stabilizer_codes` | Stabilizer codes | found.measurement, found.entanglement |
| `qec.logical_vs_physical` | Logical vs physical qubits & thresholds | qec.stabilizer_codes |
| `qec.surface_code` | Surface code | qec.stabilizer_codes |
| `qec.decoding` | Decoders & syndrome decoding | qec.surface_code |
| `qec.magic_states` | Magic states & fault-tolerant gates | qec.surface_code |
| `hw.superconducting` | Superconducting qubits | found.qubits_and_gates |
| `hw.neutral_atoms` | Neutral-atom arrays | found.qubits_and_gates |
| `hw.trapped_ions` | Trapped ions | found.qubits_and_gates |
| `hw.photonics` | Photonic quantum computing | found.qubits_and_gates |
| `hw.control_readout` | Control & readout | hw.superconducting |
| `sw.circuit_model` | Circuit model & compilation basics | found.qubits_and_gates |
| `sw.transpilation` | Transpilation & routing | sw.circuit_model |
| `sw.sdks` | Quantum SDKs (Qiskit, Cirq, PennyLane) | sw.circuit_model |
| `sw.error_mitigation` | Error mitigation | found.measurement, sw.circuit_model |
| `sw.hybrid_workflows` | Hybrid quantum-classical workflows | sw.sdks |
| `alg.grover` | Grover search | found.qubits_and_gates |
| `alg.phase_estimation` | Phase estimation & Shor | found.qubits_and_gates |
| `alg.variational` | VQE & QAOA | sw.sdks |
| `alg.simulation` | Quantum simulation | found.qubits_and_gates |
| `alg.resource_estimation` | Resource estimation | alg.phase_estimation, qec.logical_vs_physical |
| `qml.variational_circuits` | Variational circuits for ML | alg.variational |
| `qml.kernels` | Quantum kernels | found.qubits_and_gates |
| `qml.data_encoding` | Data encoding | found.qubits_and_gates |
| `qml.barren_plateaus` | Barren plateaus | qml.variational_circuits |
| `qml.hybrid_training` | Hybrid training loops | qml.variational_circuits |
| `cn.qkd` | Quantum key distribution | found.measurement |
| `cn.threat_model` | Quantum threat model (Shor's impact) | alg.phase_estimation |
| `cn.pqc` | Post-quantum cryptography | cn.threat_model |
| `cn.entanglement_distribution` | Entanglement distribution | found.entanglement |
| `cn.repeaters` | Quantum repeaters | cn.entanglement_distribution |

Career paths (1:1 with scored subfields):

| id | Title | Subfield |
|---|---|---|
| `qec_engineer` | QEC Researcher / Engineer | qec |
| `hardware_engineer` | Quantum Hardware Engineer | hardware |
| `software_engineer` | Quantum Software / Compiler Engineer | software |
| `algorithms_scientist` | Quantum Algorithms & Applications Scientist | algorithms |
| `qml_engineer` | Quantum ML Engineer | qml |
| `security_networking_engineer` | Quantum Security & Networking Engineer | crypto_net |

Each path also stores a 1–2 sentence description and `typical_titles` (the agent drafts; you review in M-07).

---

## 5. Build phases

Conventions used in every phase: **Deliverable** = what works at the end. **Manual prerequisites** = tasks from Section 2 you finish *before* delegating. **Steps** are numbered and must be done in order. **Acceptance checks** are commands/behaviors you verify yourself. **Do not** = scope fences for the agent.

Repo root folder on your machine is `Qpath`; the tree in Section 3.1 uses the name `quantum-pathfinder` only as a label.

---

### Phase 0 — Foundation

**Deliverable:** from a fresh clone, `make setup` then `make dev-backend` and `make dev-frontend` start both servers. The browser shows the app shell with a **"Backend: OK"** badge fed by `GET /api/v1/health`. The SerpApi client works in fixture mode, the taxonomy/vocabulary are seeded into SQLite, real SerpApi fixtures are recorded, and lint + tests pass.

**Manual prerequisites:** M-01, M-02, M-05 done; `AGENTS.md`, `knowledge.md`, `docs/BUILD_PLAN.md` already in the repo. M-03 and M-06 happen **mid-phase** (after step 0.5), as marked below.

**Steps**

**0.1 Repo skeleton and project files**
1. Create the folder tree from Section 3.1 (empty packages get `__init__.py`). Files that already exist (`AGENTS.md`, `knowledge.md`, `README.md`, `docs/BUILD_PLAN.md`) must **not** be overwritten; verify `AGENTS.md` matches Section 3 and report differences.
2. Create `.gitignore` (at minimum: `.env`, `*.db`, `*.sqlite*`, `.venv/`, `node_modules/`, `dist/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `coverage/`, `backend/data/`), `.editorconfig`, `.github/copilot-instructions.md` (one line pointing to `AGENTS.md`), and `docs/ARCHITECTURE.md` (headings only for now).
3. Create `Makefile` with targets: `setup`, `dev-backend`, `dev-frontend`, `test`, `lint`, `format`, `record-fixtures`, `seed-demo`. `setup` creates `backend/.venv` with `python3 -m venv`, installs `pip install -e ".[dev]"` inside it, and runs `npm ci`/`npm install` in `frontend/`. Never run `pip install` against the system Python (it is externally managed on this machine).

**0.2 Backend scaffolding**
1. `backend/pyproject.toml`: project metadata, dependencies from Section 3.2 (APScheduler pinned `>=3.10,<4`), dev extras (pytest, pytest-cov, ruff), `[tool.setuptools.packages.find] include = ["app*"]`, ruff and pytest config.
2. `app/core/config.py`: `Settings` (pydantic-settings) with every variable in Section 4.2, typed, with validators (positive cap; the fail-fast rule for live mode without a key). Expose `get_settings()` cached.
3. `app/core/logging.py`, `app/core/errors.py` (domain exceptions: `NotFoundError`, `ConflictError`, `SerpApiError`, `SerpApiCapExceeded`, `FixtureMissingError`, `LLMOutputError` + handlers returning the error shape from 4.4).
4. `app/db/base.py`, `app/db/session.py` (engine with `check_same_thread=False`, WAL pragma on connect, `SessionLocal`, `get_db`).
5. `app/main.py`: `create_app()` factory, CORS from settings, router mounted at `/api/v1`, lifespan that creates tables and runs the seed loader (scheduler hook left as a stub for Phase 5).
6. `app/api/v1/health.py` + `router.py`: `GET /health` → `{status, version, env, db}` (the `db` field comes from a trivial `SELECT 1`).

**0.3 Reference data models and seeding**
1. Models: `subfields`, `concepts`, `skills`, `career_paths`, `serpapi_call_log` (Section 4.3).
2. Create `app/data/taxonomy.json` (subfields + concepts, from 4.9), `career_paths.json` (4.9; draft descriptions/typical titles), `skills_vocab.json` (4.8; `"all"` expands to the six scored subfields).
3. `app/db/seed.py`: idempotent upsert loader with validation: every referenced id exists; concept prerequisites resolve; **no prerequisite cycles**; skill `subfield_ids` valid. Invalid data → fail at startup with a clear message.

**0.4 SerpApi client** (`app/integrations/serpapi/`)
1. `client.py` — class `SerpApiClient(settings, db_session_factory, http_client=None)` with `search(engine, params, *, fixture_variant: str) -> dict`:
   - Fixture mode: read `tests/fixtures/serpapi/<engine>__<slug(q)>__<fixture_variant>.json`; missing file → `FixtureMissingError` (callers treat it as "no more data", log it).
   - Live mode: check today's live-call count in `serpapi_call_log` against `SERPAPI_DAILY_CALL_CAP` → `SerpApiCapExceeded`; `GET https://serpapi.com/search.json` with `engine`, params and `api_key`; timeout 30 s; one retry on timeout/5xx; body with an `error` key → `SerpApiError` (except the "no results" message containing "hasn't returned any results", which returns the empty body and logs status "empty").
   - Every call (either mode) writes a `serpapi_call_log` row (engine, query, source, status). The key is never logged or stored.
2. Typed helpers: `search_jobs(query, *, location=None, gl=None, next_page_token=None, fixture_variant)` and `search_scholar(query, *, num=20, recent_only=True, fixture_variant)` (`recent_only` → `scisbd=1`). `hl=en` always.
3. `queries.py`: `QuerySpec` dataclass and the plans from Section 4.6 (`JOB_QUERY_PLAN`, `SCHOLAR_QUERY_PLAN`, `FIXTURE_PLAN`). Fixture variants: jobs `global_p1`, `global_p2`, `india_p1`; scholar `recent`.

**0.5 Fixture recorder**
1. `scripts/record_fixtures.py`: runs the `FIXTURE_PLAN` against the **live** API (requires `SERPAPI_USE_FIXTURES=false` and a key; refuses otherwise), saves pretty-printed JSON to `tests/fixtures/serpapi/` using the same naming as the client, scrubs `api_key`, skips existing files unless `--force`, prints a credit estimate before asking `y/N`, and prints a summary after.
2. **→ You now do M-03 (put the key in `backend/.env`) and M-06 (run `make record-fixtures`, inspect, confirm no key inside, commit the fixtures).** Then continue with 0.6+.

**0.6 Frontend scaffolding**
1. Create the Vite + React + TypeScript app in `frontend/`; set up Tailwind per its current official docs; add React Router, TanStack Query, Recharts, Vitest + React Testing Library, ESLint, Prettier.
2. `src/lib/apiClient.ts` (base URL from env; typed `get/post/put`; normalizes the backend error shape into a thrown `ApiError`).
3. `src/app/` (providers with `QueryClientProvider` and an error boundary, router), `components/layout/AppShell.tsx` (header with nav: **Pulse**, **Diagnostic** (disabled "coming soon"), **Method**), pages `PulsePage` (placeholder card), `MethodPage` (placeholder), `NotFoundPage`.
4. `features/health/` with a `HealthBadge` that shows "Backend: OK" / "Backend: unreachable" using `GET /health` (loading, error states included).

**0.7 Tooling and docs**
1. Configure ruff (lint + format), pytest (`testpaths`, markers), ESLint + Prettier; wire `make lint`/`make format`/`make test` (runs backend and frontend tests).
2. `README.md`: what the project is, **two-command setup**, env explanation, project structure, and a "Status" line (Phase 0).
3. Fill `docs/ARCHITECTURE.md` with the layer diagram, folder responsibilities, and the decision log so far (sync stack, SQLite + `create_all`, fixtures-first SerpApi).

**0.8 Tests**
- `test_health_returns_ok`; `test_settings_fail_fast_without_key_in_live_mode`; `test_seed_is_idempotent`; `test_taxonomy_has_no_prerequisite_cycles`; `test_skill_vocab_references_valid_subfields`.
- `test_serpapi_client_reads_fixture`, `test_serpapi_client_raises_when_fixture_missing`, `test_serpapi_client_enforces_daily_cap` and `test_serpapi_client_raises_on_error_body` (live path via `httpx.MockTransport`; no real network).
- `test_fixtures_contain_no_api_key`.
- Frontend: `HealthBadge` renders OK and error states.

**Acceptance checks**
```bash
make setup                         # succeeds, creates backend/.venv
make lint && make test             # both clean
make dev-backend                   # in one terminal
curl -s localhost:8000/api/v1/health      # {"status":"ok",...,"db":"ok"}
make dev-frontend                  # second terminal; open http://localhost:5173 -> "Backend: OK"
ls backend/tests/fixtures/serpapi | wc -l # ≈ 15-17 files (after M-06)
grep -ri "api_key" backend/tests/fixtures # prints nothing
git log --oneline | head           # several small Conventional Commits
```

**Do not:** build ingestion, any Pulse logic, Gemini code, or any model beyond those listed.
Commit and tag `phase-0`.

---

### Phase 1 — Market Pulse v1 (SerpApi jobs, no AI)

**Deliverable:** the Pulse page shows six subfield cards with **active postings, new this week (when meaningful), internship count, top companies**, an expandable posting list with apply links, an **India/Global toggle**, a dev-only **Refresh** button, and a **SerpApi activity panel**. Works fully in fixture mode (no keys, no credits) and in live mode.

**Manual prerequisites:** M-06 done (fixtures committed); M-07 (taxonomy/query plan reviewed).

**Steps**

**1.1 Models:** `job_postings`, `job_posting_subfields` (includes `tier` column: "core" or "extended"), `refresh_runs`, `pulse_snapshots` (Section 4.3). `dedupe_key` unique.

**1.2 Parsers** (`integrations/serpapi/parsers.py`)
1. `parse_job_result(raw) -> ParsedJob | None`: requires `title` and `company_name`, otherwise skip + log. Everything else via `.get()` with defaults. `apply_url` = first `apply_options[].link`, else `share_link`, else `source_link`, else `None`. `extensions` normalized to a list of strings.
2. `detect_internship(title, extensions)`: regex `\bintern(ship)?s?\b` (case-insensitive) — must not match "internal"/"international".
3. `make_dedupe_key(title, company, location)`: lowercase, strip non-alphanumerics, sha1.
4. `parse_next_page_token(raw)` from `serpapi_pagination.next_page_token`.

**1.3 Ingestion service** (`services/ingestion_service.py`)
1. `refresh_jobs(db, client, *, mode, region, subfield_ids=None)`: `bootstrap` → all queries for the chosen subfields, follow `next_page_token` up to `SERPAPI_JOBS_MAX_PAGES`; `daily` → core queries, 1 page. India region passes `location="India", gl="in"`.
2. For each parsed job: upsert by `dedupe_key` (insert with `first_seen_at=now`; otherwise update `last_seen_at`, `serp_job_id`, `is_active=true`); link to the subfield with `region`, `source_query`, and `tier` recorded from the `QuerySpec` (if a posting is found by both tiers for the same subfield, keep "core").
3. Per-query `try/except`: one failure (including `FixtureMissingError`, which just ends pagination) never aborts the run; collect errors in `refresh_runs.details`.
4. After the run: mark postings not seen for 14 days `is_active=false`; compute and upsert today's `pulse_snapshots` per subfield/region.
5. Write a `refresh_runs` row with call counts and a summary (`postings_seen`, `postings_new`, `errors`).

**1.4 Pulse service** (`services/pulse_service.py`)
- `get_pulse_cards(db, region)`: per subfield → `PulseCard.active_postings` counts core-sourced postings only, and `PulseCard` gets a separate `extra_postings` field (postings linked only via extended queries, which still appear in posting lists), plus `internship_postings`, `top_companies` (top 5), `new_this_week` and `tracking_since`. **`new_this_week` is `null` until the corpus spans ≥ 2 distinct ingestion days**; the UI then shows "tracking since <date>" instead of a misleading number. `low_data = active_postings < 8`.
- `list_postings(db, subfield_id, region, internship, limit, offset)`.

**1.5 API:** `GET /taxonomy`, `GET /pulse`, `GET /pulse/{subfield_id}/postings`, `GET /meta/serpapi-activity` (today's live calls, cap, last 20 calls, mode), `POST /admin/refresh/jobs` (header `X-Admin-Token`; body `{mode, region, subfield_id?}`; returns the run summary). Schemas: `PulseCard`, `PostingOut` (`id, title, company, location, via, apply_url, is_internship, first_seen_at, snippet` where snippet = first ~240 chars), `RefreshSummary`, `SerpApiActivity`.

**1.6 Frontend**
- `features/pulse/`: `SubfieldCard` (counts, low-data badge, top companies), `PostingList` (accordion; apply link opens in a new tab with `rel="noopener noreferrer"`), `RegionToggle`, `InternshipFilter`, `SerpApiActivityPanel`, `RefreshButton` (asks for the admin token, stores it in `sessionStorage`, dev-only affordance).
- `PulsePage` composes them. Loading skeletons, empty ("no postings captured yet — run a refresh"), and error states for each region.

**1.7 Tests**
- Parser tests on the recorded fixtures, including the India fixture that lacks `job_highlights`; malformed item is skipped; `detect_internship` table-driven (`"Quantum Intern"` yes, `"Internal Tools Engineer"` no).
- `test_refresh_jobs_is_idempotent` (run twice → same row counts, `last_seen_at` moves forward), `test_dedupe_across_queries`, `test_pagination_stops_when_fixture_missing`, `test_new_this_week_is_null_for_single_day_corpus`, `test_pulse_cards_aggregate_counts`, test proving a subfield with extra extended queries does not get a higher `active_postings` than one with only a core query when their core results are equal.
- Endpoint tests with `TestClient`: admin endpoint rejects a missing/wrong token; `GET /pulse` returns six cards.
- Frontend: card renders counts; empty state; region toggle changes the request.

**Acceptance checks**
```bash
make test
curl -s -X POST localhost:8000/api/v1/admin/refresh/jobs -H "X-Admin-Token: change-me" \
  -H "Content-Type: application/json" -d '{"mode":"bootstrap","region":"global"}'   # postings_new > 0
# run the same command again -> postings_new == 0, no duplicates
curl -s localhost:8000/api/v1/pulse | head       # 6 cards
```
In the browser: cards show counts; toggling to India changes numbers (or shows empty states); the activity panel lists fixture calls.

**Do not:** call Gemini, parse skills, or fetch Scholar. Commit and tag `phase-1`.

---

### Phase 2 — Intelligence layer (Gemini skills + Scholar themes)

**Deliverable:** each Pulse card shows **top skills (with % of postings)**, **seniority/PhD/internship mix**, and a **Research focus** strip of 3–5 themes drawn from recent Scholar papers. A subfield detail page (`/pulse/:subfieldId`) shows the full skill list, themes (each linking to its papers) and postings. AI-derived items carry an "AI-extracted" label.

**Manual prerequisites:** M-04 (Gemini key + model + rate limit in `.env`); M-09 (vocabulary reviewed). **After the phase:** M-10 (spot-check 20 postings).

**Steps**

**2.1 Models:** `job_posting_skills`, `paper_snapshots`, `research_themes`; add extraction fields to `job_postings` (already in 4.3).

**2.2 Gemini client** (`integrations/gemini/client.py`): `StructuredLLM` Protocol (`generate_structured(prompt, schema) -> BaseModel`), a real implementation using `google-genai` per Section 3.5 (rate limiter, backoff, validation, one retry on invalid output → `LLMOutputError`), and `FakeStructuredLLM` for tests.

**2.3 Prompts and schemas** (`prompts.py`, `schemas.py`) exactly as in Section 4.7 (`PostingExtraction`, `ExtractionBatch`, `Theme`, `ThemeSet`).

**2.4 Extraction service** (`services/extraction_service.py`)
1. Select postings with `extraction_status in (pending, failed)` and `extraction_attempts < 3`, in batches of 5; truncate descriptions to ~3,000 chars.
2. Call the LLM; post-validate (unknown skill ids → `unmapped_skills`, invalid subfield → null, count/ref mismatch → retry once then mark failed).
3. Persist skills (`job_posting_skills`), `seniority`, `requires_phd`, `is_internship` (rule-based OR model), `extraction_status=done`. Idempotent: never re-extract `done` postings.
4. `POST /admin/extract?limit=` runs it and returns counts (`done`, `failed`, `skipped`).

**2.5 Scholar ingestion** (`integrations/serpapi/parsers.py`, `services/research_service.py`)
1. `parse_scholar_result(raw)`: `title` required; `snippet`, `link`, `publication_info.summary`, `inline_links.cited_by.total` optional; `year` = last 4-digit year (19xx/20xx) found in the summary, else null.
2. `refresh_scholar(db, client, llm, subfield_ids)`: one query per subfield (`SCHOLAR_QUERY_PLAN`, `scisbd=1`, `num=20`), store a new `batch_id` of `paper_snapshots`, then generate themes with the LLM (validated paper indexes) and store `research_themes`.
3. `POST /admin/refresh/scholar`. **No counts or growth rates are computed from Scholar.**

**2.6 Pulse service update:** add `top_skills` (skill id, name, share of the subfield's active extracted postings), `seniority_mix`, `phd_share`, `extraction_coverage` (% of postings extracted) and `themes` (label, summary, papers with title/link). New endpoint `GET /pulse/{subfield_id}` returns this detail; `GET /pulse` cards include `top_skills[:5]` and `themes[:3]`.

**2.7 Frontend:** `SkillBars`, `MixChips` (seniority/PhD/internship), `ResearchFocus` (themes with expandable paper links), `SubfieldDetailPage` + route `/pulse/:subfieldId`, an "AI-extracted from posting text" tooltip, and an extraction-coverage note when coverage < 100%. All with loading/empty/error states.

**2.8 Tests**
- Extraction: unknown skill ids are dropped to `unmapped`; wrong item count marks the batch failed and retries once; attempts stop at 3; `done` postings are skipped; model `is_internship=false` cannot override a rule-based `true`.
- Scholar: `year` parsing table-driven (`"A Smith - Phys Rev, 2025 - nature.com"`), theme paper indexes validated, themes with no valid index dropped.
- Services use `FakeStructuredLLM`; endpoints tested end to end against fixtures.
- A test ensures no code path computes trends from `search_information.total_results`.

**Acceptance checks**
```bash
make test
curl -s -X POST "localhost:8000/api/v1/admin/extract?limit=50" -H "X-Admin-Token: change-me"   # done >= 90% of attempted
curl -s -X POST localhost:8000/api/v1/admin/refresh/scholar -H "X-Admin-Token: change-me"
curl -s localhost:8000/api/v1/pulse/qec | head -c 1200     # skills + themes present
```
Browser: skill bars and research themes render on cards; detail page works. **Then do M-10** and record your measured accuracy.

**Do not:** build the quiz, scoring, or recommendations. Commit and tag `phase-2`.

---

### Phase 3 — Orientation diagnostic

**Deliverable:** the user sets six interest sliders, answers 18 questions (one per screen, with **"Not sure"**), submits, and sees a **radar chart of readiness per subfield** with an interest overlay and per-question feedback. An anonymous profile (UUID in `localStorage`) stores results; retakes are kept as history.

**Manual prerequisites:** **M-08** — the verified quiz bank (`app/data/quiz_questions.json`, Section 6). While you finish verification, the agent may build with `ALLOW_UNVERIFIED_QUESTIONS=true` and placeholder questions; the phase is **not complete** until every one of the 18 served questions has `"verified": true` set by you.

**Steps**

**3.1 Models and seed:** `questions`, `profiles`, `assessments`. Seed questions from `quiz_questions.json` with schema validation (4 options, `correct_index` 0–3, `difficulty` 1–3, `subfield_id`/`concept_id` exist). Exclude `verified=false` unless `ALLOW_UNVERIFIED_QUESTIONS=true`. The quiz endpoint refuses (clear error) if any scored subfield has fewer than 3 servable questions.

**3.2 Schemas:** `QuizQuestionOut` (**no `correct_index`, no `explanation`**), `AnswerIn {question_id, selected_index | null}` (`null` = Not sure), `AssessmentIn {interests: dict[str,int 1–5], answers: list[AnswerIn]}`, `AssessmentOut {scores, interests, per_question: [{question_id, correct, explanation, concept_id}], weak_concepts}`.

**3.3 Quiz service** (`services/quiz_service.py`, `services/scoring_service.py`)
- `build_quiz()` returns questions ordered by `sort_order`.
- `score_assessment(...)` per Section 4.5 (difficulty points, no negative marking). Unanswered or `null` → 0. Reject unknown question ids and duplicate answers (422).
- `weak_concepts` = concepts of wrong/not-sure answers, deduplicated.

**3.4 API:** `GET /quiz`, `POST /profiles` (returns `{profile_id}`), `GET /profiles/{id}`, `POST /profiles/{id}/assessment` (stores interests on the profile, creates the assessment, returns `AssessmentOut`), `GET /profiles/{id}/assessments/latest`.

**3.5 Frontend**
- `lib/profileId.ts` (create/get UUID via `POST /profiles`, stored in `localStorage`).
- `DiagnosticPage`: `InterestStep` (six sliders with labels), `QuestionStep` (progress bar, back/next, "Not sure" button, keyboard navigable), draft answers saved to `sessionStorage` so a refresh doesn't lose progress, confirm-before-submit.
- `ResultsPage`: `ReadinessRadar` (Recharts radar with a text table alternative), `ScoreBars`, `FeedbackList` (expandable explanations; correct/incorrect/not-sure states), "Retake" action, link to Pulse.
- Enable the **Diagnostic** nav item.

**3.6 Tests**
- Scoring table-driven: all correct → 100 in every subfield; all "Not sure" → 0; mixed difficulties compute exactly (e.g. correct on difficulties 1 and 3 only → 4/6 ≈ 66.7).
- `test_quiz_endpoint_never_returns_correct_answers` (asserts the keys are absent), unverified-question exclusion, the "<3 questions per subfield" guard, invalid answer rejection.
- Frontend: stepper navigation, Not sure selection, draft persistence.

**Acceptance checks**
```bash
make test
curl -s localhost:8000/api/v1/quiz | grep -c correct_index     # 0
```
Browser: complete the quiz; results match a hand calculation of your answers; refresh mid-quiz keeps your progress; the DB contains the assessment.

**Do not:** recommend paths or call Gemini here. Commit and tag `phase-3`.

---

### Phase 4 — Path matcher (**first submittable build**)

**Deliverable:** after the diagnostic, the user sees **six career paths ranked by score** (top 3 highlighted) with a transparent breakdown (interest / readiness / demand), **live evidence** from the Pulse data (posting counts, top skills, PhD share, sample postings), and a **grounded Gemini explanation** per path. A skills picker records the user's declared skills. The full loop works end to end: Pulse → diagnostic → recommendations.

**Manual prerequisites:** Phase 3 complete with verified questions; Phase 2 data present (run extraction/scholar refresh in fixture mode); M-07 reviewed `career_paths.json`.

**Steps**

**4.1 Models:** `path_explanations` (Section 4.3). `career_paths` already seeded in Phase 0.

**4.2 Scoring** (`services/scoring_service.py`): add the pure functions from Section 4.5: `interest_n`, `readiness_n`, `demand_n`, `path_score`, `rank_paths` (tie-break: demand desc, then id), with `W_INTEREST/W_DEMAND/W_READINESS` as named module constants and a docstring explaining the rationale. `low_data` flag at `active < 8`; saturation note when ≥ 4 of 6 subfields hit the page cap in the latest bootstrap (read from `refresh_runs.details`).

**4.3 Paths service** (`services/paths_service.py`): `get_ranked_paths(db, profile_id, region="global")` — requires an assessment (else `ConflictError` → HTTP 409 with code `assessment_required`). For each path assemble evidence from `pulse_service`: `active_postings`, `internship_postings`, `top_skills`, `phd_share`, `sample_postings` (3), `low_data`. Return `PathResult {path_id, title, subfield_id, rank, score, breakdown{interest, readiness, demand, weights}, is_top3, low_data, evidence, explanation | null}`.

**4.4 Explanation service** (`services/explanation_service.py`)
1. Build the grounded JSON input from the path result (numbers and items only).
2. `evidence_hash` = hash of that JSON; return the cached `path_explanations` row if the hash matches (same profile/assessment/path).
3. Otherwise call the LLM with the Section 4.7 prompt and schema (`headline`, `reasons[3]`, `caveat`, `next_step`); validate lengths and that exactly 3 reasons exist.
4. On failure (twice) build a **deterministic template** from the same JSON, set `generated_by="template"`; never return an error to the UI for this.

**4.5 API:** `GET /profiles/{id}/paths`, `POST /profiles/{id}/paths/explanations` (batched generation for all six paths in ONE Gemini call; single-path `POST /profiles/{id}/paths/{path_id}/explanation` also supported). `PUT /profiles/{id}/skills` was cut from scope.

**4.6 Frontend**
- Route `/paths` (linked from the results page via "See your paths" button and main nav): `PathCard` ×6 with rank badge (top 3 highlighted), `ScoreBreakdown` (three labeled bars + weights, accessible table alternative), `EvidencePanel` (counts, top skills, PhD share, sample postings with safe external links), `ExplanationBlock` (loading skeleton, "AI-generated from the data shown" label, template fallback labelled honestly), `LowDataNotice`, saturation note.
- `SkillPicker`: cut per scope.
- If no assessment exists, redirect to the diagnostic with an informative banner message (`location.state.message`).
- Submission fix: `useSubmitAssessment` resolves `getOrCreateProfileId()` from storage if `profileId` is omitted or null.

**4.7 Tests**
- Scoring table-driven: zero postings everywhere (demand 0, no division by zero); one dominant subfield; tie-breaks; weights sum to 1; interest-only vs. demand-only edge cases.
- `test_ranked_paths_requires_assessment` (409), evidence assembly, explanation caching (second call does not hit the LLM), cache invalidation when evidence changes, template fallback when the fake LLM raises.
- Full flow test with fixtures + `FakeStructuredLLM`: seed postings → create profile → submit assessment → fetch six ranked paths → fetch an explanation.
- Frontend: card renders breakdown; template-labelled explanation; redirect without an assessment renders notification banner; ResultsPage "See your paths" link; `useSubmitAssessment` fallback test.

**4.8 Docs:** update README (end-to-end usage with screenshots placeholders) and `ARCHITECTURE.md`.

**Acceptance checks**
```bash
make test
# Browser: Pulse -> Diagnostic -> Results -> /paths
#   six ranked paths; changing an interest slider and retaking changes the ranking sensibly;
#   an explanation appears and only cites numbers shown in the evidence panel.
```
Check by hand: pick one path and recompute its score from the displayed interest/readiness/demand and weights — it must match.

**Milestone:** tag **`v0.1-mvp`** (and `phase-4`). If you must submit early, jump to Phase 7.

**Do not:** build the scheduler, tracking, or gap analysis. Never let the LLM change scores or ranks.

---

### Phase 5 — Opportunity tracker (continuous tracking)

**Deliverable:** the user clicks **"Track this path"**; an **Opportunities** page lists matching jobs/internships with **match scores**, an internship toggle, India/Global toggle, **"New since your last visit"** badges, and a "Last refreshed" indicator. Pulse cards gain a **trend sparkline** from daily snapshots. A scheduler (off by default) refreshes data automatically; admin can still run refreshes manually.

**Manual prerequisites:** M-12 (decide scheduler policy; keep `SCHEDULER_ENABLED=false` while developing).

**Steps**

**5.1 Profile fields and endpoints:** use `chosen_path_id` and `last_seen_at` on `profiles`. `PUT /profiles/{id}/chosen-path` (validates path id), `GET /profiles/{id}/opportunities`, `POST /profiles/{id}/seen` (sets `last_seen_at=now`). **`GET` never changes `last_seen_at`** — the frontend calls `/seen` explicitly when the user has viewed the list, so badges don't vanish on refresh by accident.

**5.2 Match service** (`services/match_service.py`): implement the posting match formula from Section 4.5 as a pure function; `null` when the posting has no extracted skills.

**5.3 Tracker service** (`services/tracker_service.py`): fetch active postings for the chosen path's subfield and region; compute `match` per posting using declared skills and the latest assessment; `is_new = first_seen_at > profile.last_seen_at` (all postings are "new" if `last_seen_at` is null **but** the response then sets `first_visit=true` so the UI doesn't shout "NEW" on everything); sort by match desc (nulls last), then `first_seen_at` desc; paginate; internship filter.

**5.4 Scheduler** (`scheduler/jobs.py`, wired in `main.py` lifespan **only if** `SCHEDULER_ENABLED`)
- `BackgroundScheduler` with three cron jobs from env: daily global core jobs refresh (+ extraction of new postings), weekly India core refresh, weekly Scholar refresh + themes.
- Each job: opens its **own** DB session, catches all exceptions into `refresh_runs`, respects the daily call cap, `max_instances=1`, `coalesce=True`; shuts down cleanly with the app.
- `GET /meta/refresh-status` returns the last run per kind (time, status, calls, counts); `GET /pulse/{subfield_id}/trend` returns snapshot series (date, active, new, internships).

**5.5 Frontend:** `TrackPathButton` on `PathCard`; `OpportunitiesPage` (route `/opportunities`; nav item enabled once a path is tracked) with `OpportunityCard` (match badge or "not enough info", `NEW` badge, apply link), filters (internship, region), `LastRefreshedPill`, "Mark all as seen" (calls `/seen`), `TrendSparkline` on Pulse cards (renders only with ≥ 2 snapshots; otherwise "tracking started <date>").

**5.6 Tests**
- Match formula table-driven (including `null`); `is_new` logic with controlled timestamps (no `sleep`); `first_visit` behavior; `GET` leaves `last_seen_at` unchanged, `POST /seen` updates it.
- Scheduler: job registration reflects env flags; a job failure writes a failed `refresh_runs` row and does not crash; overlapping runs are prevented (test by invoking twice with a held lock).
- Trend endpoint returns ordered series; frontend tests for badges and the sparkline hidden state.

**Acceptance checks**
```bash
make test
# Simulate two days: run a bootstrap refresh, then insert/modify first_seen_at on a few postings
# (via a test helper or SQL) and re-fetch /opportunities -> only the newer ones are is_new=true.
# Set SCHEDULER_ENABLED=true briefly: GET /meta/refresh-status shows jobs registered; set it back to false.
```
Browser: track a path, see matched opportunities, mark as seen, badges clear.

**Do not:** send emails/notifications, track per user in SerpApi, or enable the scheduler permanently during development. Commit and tag `phase-5`.

---

### Phase 6 — Gap analysis and learning path (stretch)

**Deliverable:** for the tracked path, a **ranked skill-gap list** (what employers ask for × what you lack) and an **ordered concept learning plan** that respects prerequisites. Users mark concepts complete and the plan updates. Each concept explains **why it matters** ("appears in N postings").

**Manual prerequisites:** M-11.

**Steps**

**6.1 Skill→concept mapping:** the agent proposes `concept_ids` for each skill in `skills_vocab.json` (only where a real relationship exists; many skills legitimately have none) and lists its choices in a short review note. **You approve or edit (M-11) before step 6.2.**

**6.2 Gap service** (`services/gap_service.py`): formulas from Section 4.5 (`freq_k`, `proficiency_k`, `gap_k`); input = chosen path's subfield, declared skills, latest assessment; output = ranked list `{skill_id, name, frequency, proficiency, gap, n_postings}`, top 8 flagged.

**6.3 Plan service** (`services/plan_service.py`): collect concepts from the top gap skills, add transitive prerequisites, drop completed, topologically sort (Kahn) with tie-break by summed gap weight desc then id; each item carries `why` ("N postings mention <skills>") and `prerequisites`. Detect cycles defensively (raise a data error).

**6.4 API:** `GET /profiles/{id}/gap-analysis`, `GET /profiles/{id}/plan`, `PUT /profiles/{id}/plan/concepts/{concept_id}` (`{completed: bool}`; unknown concept → 404). Requires a chosen path (409 `path_required` otherwise).

**6.5 Resources:** `app/data/resources.json` = `{concept_id: [{title, url}]}`, **hand-curated by you**, validated at seed time (URL must start with `https://`, title non-empty). Never generated by an LLM. Concepts without resources simply show none.

**6.6 Frontend:** `PlanPage` (route `/plan`): `GapChart` (bar chart + table alternative), `ConceptTimeline` (ordered cards with prerequisite chips, why-it-matters, resources, completion toggle), progress bar. Link from Opportunities ("skills these postings want that you lack").

**6.7 Tests:** gap math table-driven; topological order respects every prerequisite (property-style test over the real taxonomy); completed concepts excluded; cycle detection; endpoint tests; frontend completion toggle updates the list.

**Acceptance checks:** for a profile weak in error correction who tracks `qec_engineer`, the plan shows foundations before stabilizer codes before surface code before decoding; marking a concept complete removes it and reorders nothing illegally.

**Do not:** invent resource links or add pages beyond `/plan`. Commit and tag `phase-6`.

---

### Phase 7 — Submission hardening

**Deliverable:** a **judge-ready repository**: a Method & Data page, a README that gets a stranger running in two commands, an honest account of data limits, a demo script, and a clean history with no secrets.

**Manual prerequisites:** M-12 (enable the scheduler **≥ 4 days before the deadline** so real history accumulates), M-13, M-14, M-15.

**Steps**

**7.1 Method & Data page:** `GET /meta/method` + `MethodPage`: data sources and engines used; refresh cadence; **what each number means** (counts are a sampled indicator, not a census; Scholar themes are qualitative; no trends from Scholar totals); AI-extraction accuracy from M-10 (a number you supply in a small `docs/DATA_AND_METHOD.md`); SerpApi usage by engine (from `serpapi_call_log`); the scoring formula and weights; known limits (thin subfields, India volume, vocabulary coverage).

**7.2 Demo data policy (honesty rule):** the preferred history is **real**: the scheduler's snapshots from the final days. If real history is too short, `scripts/seed_demo_history.py` may generate a **synthetic** series, and with `DEMO_MODE=true` the UI must label it clearly (**"Synthetic demo data"**) on every chart that uses it. Never present synthetic data as real.

**7.3 README:** pitch; screenshots; a short architecture diagram; **two-command setup** (`make setup`, then the two dev commands); required env vars (fixture mode needs none); a table of SerpApi engines used and **why each is material** (jobs → every pulse number, skills, feed and tracking; Scholar → research themes); AI tools used (Freebuff, Antigravity CLI, Copilot, Gemini API at runtime); limitations; license. State plainly that this is a new project that shares design ideas with Ananta.

**7.4 Hygiene:** LICENSE present; `.env.example` complete; DB and venv ignored; fixtures contain no keys (test exists); `make lint` and `make test` clean; frontend `npm run build` passes; remove dead code and stray TODOs; commit messages tidy (no giant squashes).

**7.5 Quality pass:** keyboard navigation through the main flow; loading/empty/error states checked on every page; no console errors; responsive at laptop width.

**7.6 `docs/DEMO_SCRIPT.md`:** a 3-minute shot list: (1) Pulse with the SerpApi activity panel and a live "Refresh now" (≈ 25 s); (2) diagnostic quick run (≈ 35 s, pre-filled); (3) ranked paths and one grounded explanation (≈ 40 s); (4) tracked opportunities with NEW badges and last-refreshed pill (≈ 30 s); (5) plan (if built) (≈ 25 s); (6) Method page and repo structure (≈ 25 s). Show the app running **locally**.

**Acceptance checks**
```bash
git clone <your repo> /tmp/qp-check && cd /tmp/qp-check
make setup && make test               # works from a clean clone with no .env (fixture mode)
# follow the README only; the app must start and the full flow must work
```
Then M-13 (secret scan), make the repo public, M-14, M-15. Tag `v1.0-submission`.

---

## 6. Quiz question verification method

**Why this matters:** judges and users who know quantum computing will notice a wrong question immediately, and an LLM will happily write confident, wrong physics. Questions are served only if **you** set `"verified": true`.

### 6.1 What to author

- **18 questions**, 3 per scored subfield: difficulty **1** (definition/recognition), **2** (applied), **3** (reasoning). Write 24–30 drafts and keep the best 18.
- Conceptual and answerable in under a minute; no heavy math; no vendor trivia that goes stale; four options; exactly one defensible answer; distractors are *plausible misconceptions*; no "all of the above"; no trick wording.
- Tag each with `concept_id` from Section 4.9.

### 6.2 Data format (`app/data/quiz_questions.json`)

```json
{
  "id": "qec-1",
  "subfield_id": "qec",
  "concept_id": "qec.stabilizer_codes",
  "difficulty": 1,
  "stem": "In a quantum error-correcting code, what do syndrome measurements do?",
  "options": [
    "They read out the value of the encoded logical qubit",
    "They reveal information about which error occurred without revealing the encoded logical information",
    "They reset all physical qubits to the zero state",
    "They apply the logical gate to the encoded data"
  ],
  "correct_index": 1,
  "explanation": "Syndrome measurements extract error information while leaving the encoded logical state undisturbed.",
  "source_refs": ["<book/paper + chapter or section you checked>"],
  "verified": false,
  "verified_by": "",
  "verified_on": ""
}
```
(The example is illustrative; verify it like any other question before setting `verified`.)

### 6.3 Drafting with Gemini (optional)

```text
Draft 6 multiple-choice questions for the quantum computing concept "<concept name>"
(subfield: <subfield>), two each at difficulty 1, 2 and 3.
Constraints: four options, exactly one correct, conceptual (no long calculations),
distractors must be plausible misconceptions, no "all of the above". For each, give
a one-sentence explanation and name the textbook topic where the answer can be checked.
Output JSON matching this schema: <paste the schema above>.
```
Treat every output as an **unverified draft**.

### 6.4 The verification procedure (do all steps for every question)

1. **Locate the answer in an authoritative source** and write the reference into `source_refs`. If you cannot find it in a textbook, review article or official document, drop or rewrite the question.
2. **Check the stem for ambiguity**: could a knowledgeable person defend a second option? If yes, rewrite.
3. **Check every distractor is actually wrong**, and note *why* (this becomes the explanation).
4. **Blind cross-check:** ask a *different* model (or a fresh chat) to answer the question without the key. If it disagrees, investigate — the disagreement is often an ambiguous stem, sometimes a wrong key.
5. **Compute, don't recall:** for any question involving circuit outputs, state probabilities or gate identities, **simulate it** in Qiskit/Cirq (or by hand) and confirm.
6. **Time-sensitivity check:** does the answer depend on a record, a vendor claim, or a recent result that could change? If so, rephrase around the durable concept.
7. **Peer spot-check:** have a classmate, senior, or lecturer solve ~20% of the questions, especially the difficulty-3 ones, and note confusion.
8. **Sign off:** only then set `verified: true`, `verified_by`, `verified_on`.

**Per-question log (keep in a sheet or `docs/QUIZ_VERIFICATION.md`):**

| id | source checked | blind cross-check agrees? | simulated/computed? | distractors explained | peer check | verified |
|---|---|---|---|---|---|---|

### 6.5 Suggested authoritative sources (confirm exact chapters/sections yourself)

| Area | Sources |
|---|---|
| Foundations, algorithms | Nielsen & Chuang, *Quantum Computation and Quantum Information*; IBM Quantum Learning (the former Qiskit Textbook); Preskill's lecture notes |
| Error correction | Nielsen & Chuang (error-correction chapters); Gottesman's thesis on stabilizer codes; Fowler et al. 2012, "Surface codes: Towards practical large-scale quantum computation" |
| Hardware | Kjaergaard et al. 2020 (superconducting qubits review); Bruzewicz et al. 2019 (trapped-ion review); Henriet et al. 2020 (neutral atoms); Kok et al. 2007 (linear-optical quantum computing) |
| Software / mitigation | Qiskit and Cirq official docs; Preskill 2018, "Quantum Computing in the NISQ era and beyond"; Temme et al. 2017 (error mitigation) |
| Algorithms | Nielsen & Chuang; Cerezo et al. 2021, "Variational quantum algorithms" |
| Quantum ML | Biamonte et al. 2017, "Quantum machine learning"; McClean et al. 2018 (barren plateaus); Havlíček et al. 2019 (quantum feature spaces) |
| Cryptography / networking | NIST FIPS 203, 204 and 205 (post-quantum standards); Gisin et al. 2002, "Quantum cryptography"; Wehner, Elkouss & Hanson 2018, "Quantum internet: a vision for the road ahead" |

I could not verify page numbers or exact section titles; check the citations yourself.

### 6.6 Red flags (rewrite or delete)

Two options that are both arguably correct; a stem that depends on a convention (qubit ordering, sign) without stating it; "always/never" claims; questions answerable by test-taking tricks (longest option wins); anything you could only verify by asking the same LLM that wrote it.

### 6.7 Difficulty calibration

Take the quiz yourself and with two friends of different levels. Difficulty-1 questions should be answered correctly by nearly everyone with basic exposure; difficulty-3 should split people. Adjust the tags (not the scoring weights) accordingly.

---

## 7. Submission checklist

- [ ] Repo is **public**, setup works from a clean clone (README only), `make test` green (M-13 secret scan done, no keys in history or fixtures).
- [ ] Demo video **< 3 minutes**, shows the project **running locally** with SerpApi data driving the main screens; link opens in a private window (M-14).
- [ ] Track chosen: **Knowledge & Public Interest**.
- [ ] Project description covers *what it does, who it helps, how SerpApi is used*. Draft:
  > QPath helps students and early-career engineers decide where to specialize in quantum computing. It uses SerpApi's **Google Jobs** engine to continuously capture live quantum job and internship postings per subfield (the source of every demand number, skill ranking, tracked opportunity and "new since your last visit" badge) and **Google Scholar** to surface what recent research in each subfield is about. A short diagnostic measures the user's readiness and interests; deterministic scoring combines these with live demand to rank career paths, and Gemini only extracts structure from postings and explains results using the supplied data. Without SerpApi the app would have no market signal to recommend from.
- [ ] Pre-existing project? → new project; mention it shares design ideas with Ananta Quantum Studio (M-15).
- [ ] AI tools disclosed: Freebuff, Antigravity CLI, GitHub Copilot, Claude (planning/consultation), Gemini API (runtime).
- [ ] Participant details ready; Rules and Terms accepted; **press "Submit project" before Oct 10, 2026, 23:59 IST** (a saved draft does not count).
- [ ] Submit early — the site records the first submission time and you can edit afterwards.

---

## 8. Risks and fallbacks

| Risk | Likelihood | Fallback |
|---|---|---|
| Thin posting volume for some subfields (esp. India, crypto/networking) | High | Global default + India toggle; `low_data` flags; the Method page reports it honestly (a finding, not a bug) |
| Gemini extraction errors or hallucinated skills | Medium | Controlled vocabulary + validation; measure accuracy in M-10 and publish it; unmapped skills never counted |
| Gemini free-tier limits or model changes | Medium | Env-driven model/rate; batching and persistence; fixtures-based dev; template fallback for explanations |
| Quiz questions contain errors | Medium | Section 6 procedure; unverified questions never served; peer spot-check |
| SerpApi credit exhaustion | Medium | Fixture mode, daily cap, scheduler off during dev; ask organizers for credits (M-16) |
| Scholar yields noisy results | Medium | Themes are qualitative and show source papers; drop the research strip if unusable (Pulse still stands on Jobs) |
| Not enough real history for "tracking" | Medium | Enable scheduler ≥ 4 days before deadline; else clearly labeled synthetic series |
| Vibe-coded code the owner can't explain | Medium | Comment rules (3.8), `ARCHITECTURE.md` per phase, and reading each phase's diff before tagging |
| Schedule slip | High | Cut line: Phase 4 submittable → Phase 7 → then Phase 5/6 if time remains |
| Judges see "just another jobs dashboard" | Medium | Lead the demo with the diagnostic → ranked paths → tracked decision, not the feed; emphasize the research-to-career decision layer qubitsok-style aggregators lack |

*End of build plan.*
