# Quantum Pathfinder — Build Plan & Project Context

> Working name: **Quantum Pathfinder**. Created 2026-10-03 for the SerpApi India Hackathon 2026.
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

- Builder: Aprajit, first-year B.Tech CSE (AI & ML) student. Also building **Ananta Quantum Studio** (a browser-based quantum education/research platform). Quantum Pathfinder is a **separate, standalone project** born from one planned Ananta feature.
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

**Closest competitor to the chosen idea:** *qubitsok.com* — a live quantum jobs + research-papers aggregator/newsletter (crawls ~20 sources weekly, classifies with NLP; ~780 job and ~540 paper subscribers at the time checked). It is a **passive aggregator**. Quantum Pathfinder differs by **connecting live signal to a personalized decision**: diagnostic → ranked paths → gap analysis → tracked opportunities. Do **not** drift into "a list of jobs" or "a list of papers" without a decision layer; that shape is already owned.

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

- Submit Quantum Pathfinder as its **own repo**, README and demo. Do **not** demo Ananta (it would dilute the "SerpApi is essential" story). Mention Ananta as related work only; disclose truthfully that Pathfinder is a new project that shares design ideas (the taxonomy) with Ananta.
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
6. Timeouts: 30 s. Retry once on timeout/5xx; never retry 4xx. A response body containing an `error` field is a `SerpApiError`.
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
| `job_posting_subfields` | `posting_id`, `subfield_id`, `region` (`global`/`india`), `source_query`, `first_seen_at`, `last_seen_at` | Subfield tag comes from the query that found it, plus the model's `primary_subfield_id` |
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
- `demand_n(s) = ln(1 + active_s) / ln(1 + max_active)`; `0` if `max_active = 0`. (Log scale stops one big subfield from flattening the rest.) `active_s` = active postings tagged to subfield `s` for the selected region.

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

