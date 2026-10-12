# Architecture — QPath

> Last updated: Phase 5 (Opportunity tracker). Updated at the end of every phase per AGENTS.md 3.8.7.

---

## Overview

QPath is a live-data career navigator for quantum computing. It pairs real job-market data (via SerpApi Google Jobs and Google Scholar) with deterministic scoring and structured AI output (Gemini) to deliver personalised career path recommendations and skill-gap plans.

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

### Product renamed to QPath (2026-10-12)

A pure display/branding rename from "Quantum Pathfinder" to "QPath" (capital Q, capital P, no
space). No behaviour, scoring, data, API shape or test intent changed — only names shown to users
(header, footer, document title, 404 copy), the FastAPI/OpenAPI title ("QPath API"), package
description metadata, and documentation sources (README, BUILD_PLAN, DATA_AND_METHOD, AGENTS,
summary). The Method page still renders `docs/DATA_AND_METHOD.md` verbatim, which was updated in
place. Regression tests: `test_openapi_title_contains_qpath` (backend, `test_health.py`) and
`src/AppShellRename.test.tsx` (frontend: header, footer, document title, 404 wordmark).

Identifiers **deliberately kept** (renaming would break behaviour or existing data):

| Identifier | Why kept |
|---|---|
| `localStorage`/`sessionStorage` keys `quantum_pathfinder_profile_id` and `quantum_pathfinder_diagnostic_draft` | Renaming orphans every existing profile id and dev admin token (Step 3 freeze) |
| `pathfinder.db` in the `DATABASE_URL` default and `.env.example` | Default database filename; renaming would point existing environments at an empty DB |
| npm package names `qpath-frontend`/`qpath-backend` (display metadata only; lock file updated) | Package names are identifiers; the repo URL already says `Qpath` |
| Python package name `app` | Module name, unrelated to the brand |
| API routes and JSON field names | Public API contract unchanged |
| Recorded fixtures and git history | Data never synthesized or rewritten |

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


---

## Phase 3 — Orientation diagnostic

### What was added

**Backend**

- **Models:** `questions`, `profiles`, `assessments` tables (`app/models/quiz.py`, `app/models/profile.py`). The `profiles` table already carries the Phase 5 columns (`chosen_path_id`, `last_seen_at`, `declared_skills`, `completed_concepts`) to avoid a later schema change.
- **Seeding:** `seed_quiz_questions` in `app/db/seed.py` validates and upserts `app/data/quiz_questions.json` (exactly 4 options, `correct_index` 0–3, `difficulty` 1–3, resolvable `subfield_id`/`concept_id`), running after the reference seed in the lifespan.
- **Services:** `services/scoring_service.py` holds the pure scoring functions (difficulty-weighted readiness, `weak_concepts`, `per_question_feedback`); `services/quiz_service.py` handles the servable-question guard, anonymous profiles and assessment persistence.
- **API:** `GET /quiz`, `POST /profiles`, `GET /profiles/{id}`, `POST /profiles/{id}/assessment`, `GET /profiles/{id}/assessments/latest`. New domain errors: `QuizContentError` (503, `quiz_insufficient_questions`) and `InvalidAssessmentError` (422, `invalid_assessment`).

**Frontend**

- `features/diagnostic/` — `api.ts`, `hooks/useDiagnostic.ts` (TanStack Query), `draft.ts` (sessionStorage draft), and components `InterestStep`, `QuestionStep`, `ReadinessRadar` (Recharts radar + accessible table), `ScoreBars`, `FeedbackList`.
- `pages/DiagnosticPage.tsx` (stepper: interests → one question per screen → review/confirm → submit) and `pages/ResultsPage.tsx` (radar, bars, feedback, retake). Routes `/diagnostic` and `/diagnostic/results`; the nav item is enabled.
- `lib/profileId.ts` gained `ensureProfileId()`: the localStorage UUID is synced with the backend via idempotent `POST /profiles`.

### Data flow

```
GET /quiz → quiz_service.build_quiz
  ├─ filter questions by Settings.allow_unverified_questions (serve-time)
  └─ guard: every scored subfield needs ≥ 3 servable questions, else 503
POST /profiles/{id}/assessment → quiz_service.submit_assessment
  ├─ validate interests cover exactly the six scored subfields (422)
  ├─ scoring_service.normalize_selections (unknown id / duplicate → 422)
  ├─ scoring_service.readiness_scores: readiness_s = 100 × earned / available,
  │  earned = sum of difficulties of correct answers; null/absent = 0
  ├─ store raw answers + scores on `assessments`; interests onto `profiles`
  └─ return AssessmentOut (per-question feedback + weak_concepts)
```

### Decision log (Phase 3)

- **Serve-time verified filtering (deviation from plan 3.1):** the plan seeds only verified questions; this build seeds **all** questions with their owner-controlled `verified` flag and filters at request time from `Settings`. Same observable behavior, but flipping `ALLOW_UNVERIFIED_QUESTIONS` does not require a reseed. While the bank is placeholder content the dev `.env` sets the flag to `true`; the owner flips it back after M-08.
- **Answer leakage is structurally impossible:** `QuizQuestionOut` does not declare `correct_index`/`explanation`, so ORM columns cannot serialize; a test asserts the raw response body never contains those keys, and the integration suite re-checks them against the DB directly.
- **Feedback is derived, not stored:** `GET .../assessments/latest` recomputes per-question feedback from the stored raw answers, so correcting an explanation or key immediately fixes the history view.
- **Skipping questions is allowed:** "Next" is always available; unanswered questions score 0 like "Not sure", and the review step warns with a count before submission.
- **Interests are validated strictly:** unknown or missing scored subfields are 422 — a partially-specified diagnostic would silently distort Phase 4 path scores.

### Known limits (Phase 3)

- `quiz_questions.json` now contains **18 real questions / 0 verified / 0 placeholder** (all stems are real content from docs/quiz_confirmed.md, verified=false awaiting owner sign-off M-08). The bank has exactly 3 questions per scored subfield at difficulties 1, 2, 3.
- Concept ID choices: algorithms-1 uses `found.qubits_and_gates` because no complexity-class concept exists in taxonomy.json (reported as open question).
- The seeder now prunes questions whose id is not in the JSON, preventing stale placeholder rows from surviving in existing dev databases.
- The diagnostic does not yet feed anything downstream: path matching (Phase 4) will consume `readiness_scores` and profile interests.
- No Gemini usage in this phase (per plan).
- Owner must still verify all 18 questions (manual task M-08, BUILD_PLAN Section 6) and set `ALLOW_UNVERIFIED_QUESTIONS=false` before submission.


---

## Phase 4 — Path matcher (backend)

### What was added

**Backend**

- **Models:** `path_explanations` table (`app/models/path_explanation.py`), storing `(profile_id, assessment_id, path_id, evidence_hash)` unique cache keys, JSON payload, and `generated_by` ("llm" | "template").
- **Scoring:** pure deterministic scoring in `app/services/scoring_service.py`: `interest_n`, `readiness_n`, `demand_n` (log-compressed), `path_score` (40% interest, 30% demand, 30% readiness), `rank_paths` (tie-break: demand desc, then path id), and `saturation_note`.
- **Services:**
  - `services/paths_service.py`: `get_ranked_paths`, `get_ranked_paths_with_explanations`, `request_explanation`. Requires diagnostic assessment (409 `assessment_required`). Assembles live Pulse evidence: active postings (core-tier only for fairness), internship count, top skills, PhD share, sample postings, and flags (`low_data`, `saturated`).
  - `services/explanation_service.py`: batched grounded explanations (`PathExplanationsBatch`). Validates numbers in LLM output against evidence JSON (`validate_numbers`); rejects hallucinations and falls back to deterministic template (`build_template`). Handles `GeminiDailyQuotaExhausted` by immediate degradation to templates without retrying.
- **API:**
  - `GET /profiles/{id}/paths`: returns 6 ranked paths with score breakdown, evidence, and cached explanation (if generated) or null.
  - `POST /profiles/{id}/paths/explanations`: batched explanation generation for all 6 paths; returns all 6 paths with populated explanations.
  - `POST /profiles/{id}/paths/{path_id}/explanation`: generates batch and returns single path explanation.
- **Tests:** unit tests for pure scoring & explanation validators (`test_scoring_service.py`, `test_explanation_service.py`), and full integration suite (`test_paths_api.py`) covering 409 guard, evidence assembly, caching, cache invalidation, template fallbacks, and number validation.

### Data flow

```
GET /profiles/{id}/paths → paths_service.get_ranked_paths
  ├─ check latest assessment exists (else 409 AssessmentRequiredError)
  ├─ load 6 scored subfields and linked CareerPath definitions
  ├─ gather Pulse details: core active postings, internships, top skills, PhD share, samples
  ├─ scoring_service.rank_paths: 100 * (0.40*interest + 0.30*demand + 0.30*readiness)
  ├─ explanation_service.cached_explanations: attaches matching hash rows (no LLM call)
  └─ return PathsOut

POST /profiles/{id}/paths/explanations → paths_service.get_ranked_paths_with_explanations
  ├─ assemble ranked paths and current evidence hashes
  ├─ fetch cached rows matching evidence_hash
  ├─ if any missing:
  │    ONE batched Gemini call via StructuredLLM for missing paths
  │    validate each item against word budgets AND validate_numbers (against evidence JSON)
  │    on schema failure, number hallucination, LLM error, or GeminiDailyQuotaExhausted:
  │      degrade to build_template (generated_by="template")
  │    persist fresh cache rows in path_explanations
  └─ return PathsOut with all explanations populated
```

### Decision log (Phase 4)

- **Batched explanation endpoint (`POST /profiles/{id}/paths/explanations`):** The build plan specified `POST /profiles/{id}/paths/{path_id}/explanation`. Because Gemini API calls are expensive and subject to strict quotas, `explanation_service` generates explanations for all 6 paths in ONE batched LLM request (`PathExplanationsBatch`). We exposed `POST /profiles/{id}/paths/explanations` as the primary batched endpoint returning all 6 paths with explanations, while preserving `POST /profiles/{id}/paths/{path_id}/explanation` for single-path requests.
- **Strict numeric grounding (`validate_numbers`):** LLM explanations are only allowed to cite numbers that actually appear in the evidence JSON passed to the model. Any hallucinated number causes the specific path's explanation to be rejected and replaced by a deterministic template (`generated_by="template"`), ensuring factuality.
- **Zero failure for UI on LLM errors:** The paths and explanation endpoints never return 500 or 502 to the UI due to Gemini issues. When Gemini is unconfigured, raises an error, or hits quota, the deterministic template fallback guarantees a 200 response with transparent provenance.
- **Core-tier demand isolation:** In alignment with Phase 1 fairness rules, only core-tier query postings feed `active_postings` and normalized demand scoring, preventing query-count imbalances across subfields from distorting rankings.

### Known limits (Phase 4)

- Declared skills carry-over (implemented after the phase, on branch `skillp`): `PUT /profiles/{id}/skills` and the frontend `SkillPicker` are now DONE — the cut item below no longer applies.
  - ~~Declared skills picker (`PUT /profiles/{id}/skills`) was intentionally cut from this phase's scope per user instruction.~~ (Reimplemented as the Phase 4 carry-over; see decision log below.)
- The 18 quiz questions in `quiz_questions.json` remain `verified=false` awaiting owner verification in M-08.

---

## Phase 4 frontend (plan 4.6)

> Added in Phase 4 frontend completion.

**Route:** `/paths` — linked from both the nav bar ("Paths") and the ResultsPage "See your paths" button.

### Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `PathsPage` | `src/pages/PathsPage.tsx` | Page shell: fetch paths, trigger explanation mutation, display 6 `PathCard`s, accessible score table |
| `PathCard` | `src/features/paths/components/PathCard.tsx` | One ranked path: rank badge (cyan for top 3), score, `ScoreBreakdown`, collapsible `EvidencePanel` + `ExplanationBlock`, `LowDataNotice` |
| `ScoreBreakdown` | `src/features/paths/components/ScoreBreakdown.tsx` | Three labelled ARIA `progressbar`s (interest/demand/readiness) with weights; formula caption enables manual verification (plan 4.8 acceptance check) |
| `EvidencePanel` | `src/features/paths/components/EvidencePanel.tsx` | Posting counts, PhD share, top-skills inline bars, sample postings with safe external links |
| `ExplanationBlock` | `src/features/paths/components/ExplanationBlock.tsx` | Loading skeleton; honest provenance label ("AI-generated from the data shown" vs "Template fallback (deterministic)"); headline/reasons/caveat/next-step |
| `LowDataNotice` | `src/features/paths/components/LowDataNotice.tsx` | Amber notice when `low_data=true` (< 8 active postings) |

### Hooks / API

| Module | File | Responsibility |
|--------|------|----------------|
| `usePaths` | `src/features/paths/hooks/usePaths.ts` | `useQuery` over `GET /profiles/{id}/paths`; staleTime 5 min |
| `useRequestExplanations` | same | `useMutation` over `POST /profiles/{id}/paths/explanations`; updates query cache on success |
| `getRankedPaths`, `requestExplanations` | `src/features/paths/api.ts` | Thin wrappers through `apiClient` |

### Frontend data flow

```
PathsPage
  ├─ usePaths → GET /profiles/{id}/paths (6 ranked paths, explanations=null if not yet generated)
  │     409 → <Navigate to="/diagnostic" state={{ message: "..." }} replace />
  │           DiagnosticPage catches state and displays an informative banner
  ├─ useRequestExplanations → POST /paths/explanations (ONE batched Gemini call server-side)
  │     onSuccess: updates query cache — no extra re-fetch needed
  └─ PathCard × 6
        ├─ ScoreBreakdown   (always visible)
        ├─ EvidencePanel    (collapsible)
        └─ ExplanationBlock (collapsible; loading=true while mutation is pending)
```

### Decision log (Phase 4 frontend)

- **Accessible score table:** The breakdown bars are visual-only; an accessible `<table>` under a `<details>` element provides a text alternative for screen readers (AGENTS.md 3.6.6 "charts have a text alternative").
- **Phase badge removed:** `AppShell` header badge ("Phase 0") removed completely per UI simplification requirements.
- **"Paths" nav link added:** The global nav now includes Pulse / Diagnostic / Paths / Method.
- **"See your paths" button:** Prominent button on `ResultsPage` linking directly to `/paths`.
- **Diagnostic redirect banner:** If `/paths` receives HTTP 409 (`assessment_required`), it redirects to `/diagnostic` passing notification state, rendering an informative banner explaining that the orientation diagnostic is required first.
- **Profile ID resolution in `useSubmitAssessment`:** Fixed `useSubmitAssessment` to resolve `getOrCreateProfileId()` from storage when `profileId` is omitted or null, preventing "Profile is not ready yet" mutation rejections on submission.
- **SkillPicker cut:** ~~`PUT /profiles/{id}/skills` and the frontend skills multi-select were intentionally cut per user instruction.~~ Reimplemented later as the Phase 4 carry-over on branch `skillp` (see Phase 4 carry-over section below).
- **Known limits (Phase 4 frontend):** the 18 quiz questions in `quiz_questions.json` remain `verified=false` awaiting owner verification in M-08.

### Known limits (Phase 4 frontend)

- `ExplanationBlock` collapses by default; users can click "Show explanation" to inspect.
- The 18 quiz questions in `quiz_questions.json` remain `verified=false` awaiting owner verification in M-08.

---

## Phase 4 carry-over — declared skills (branch `skillp`)

> The one item cut from Phase 4, implemented afterwards per user instruction. NOT a new
> phase: no scoring/ranking/explanation logic changed, and no Phase 5/6 work started.

### What was added

**Backend**

- `app/schemas/skills.py`: `SkillOut`, `DeclaredSkillsIn`.
- `app/services/skills_service.py`: `list_skills` (vocabulary sorted by name, ties by id) and
  `replace_declared_skills` (atomic: profile resolved first, then vocabulary validation; only
  `declared_skills` is assigned — interests, `last_seen_at`, `chosen_path_id`,
  `completed_concepts` and assessment history are never touched). Duplicates are removed
  keeping first-seen order; an empty list clears the list; no hardcoded cap — the only upper
  bound is the size of the vocabulary (53 entries in `skills_vocab.json`).
- `app/api/v1/skills.py` + router wiring: read-only `GET /skills` returning a bare list
  `[{id, name, aliases, subfield_ids}]` sorted by name (exactly the shapes the task spec named;
  no wrapper object), recorded here because it is not in the Section 4.4 API table.
- `PUT /profiles/{id}/skills` (thin route on the profiles router) with body
  `{"skill_ids": [str, ...]}`. Validation errors: unknown ids → 422 `invalid_skills` listing
  the offending ids, nothing written; missing/non-string items → 422 `validation_error` at the
  schema boundary; unknown profile → the existing 404 `not_found`.
- `ProfileOut` now exposes `declared_skills` (additive field, defaults to `[]`).

**Frontend**

- `features/skills/` (new feature): `api.ts` (GET /skills, PUT declared skills),
  `hooks/useSkills.ts` (`useSkills` with 1-hour staleTime; `useProfile`; `useSaveDeclaredSkills`
  updating the profile query cache on success), `components/SkillPicker.tsx` (searchable
  multi-select; filter is case-insensitive over name AND aliases — typing “mwpm” finds
  PyMatching; removable chips; Save button; saved confirmation; aria-live selection count;
  loading/empty/error-with-retry states; fully keyboard-operable with accessible names),
  `components/DeclaredSkillsPanel.tsx` (collapsible panel “Skills you already have (optional)”).
- Mounted on `/paths` (`PathsPage`), pre-filled from the profile. Copy is honest: the list is
  saved to the profile and does NOT change the ranking.
- `types/api.ts`: `SkillOut`, `SkillsListResponse`, `DeclaredSkillsRequest` added;
  `ProfileResponse` gained `declared_skills`.

### Data flow

```
GET  /skills                        → skills_service.list_skills → vocabulary (sorted by name)
PUT  /profiles/{id}/skills          → skills_service.replace_declared_skills
                                       ├─ quiz_service.get_profile (404 gate)
                                       ├─ vocabulary validation (dedupe, 422 invalid_skills)
                                       └─ profile.declared_skills = validated → commit
PathsPage → DeclaredSkillsPanel → SkillPicker (GET /skills + useProfile pre-fill)
                                       └─ Save → PUT → profile query cache updated
```

### Decision log (carry-over)

- **`GET /skills` added outside the plan's API table.** The build plan's Section 4.4 surface
  does not list a vocabulary endpoint, but the frontend must show the controlled vocabulary
  and no endpoint exposed it. Recorded here as the required addition: read-only, derived
  entirely from the seeded `skills` table, no SerpApi/Gemini involvement.
- **`ProfileOut` gained `declared_skills` (additive).** The picker pre-fills from the profile;
  until now no endpoint returned `declared_skills`. Phase 5 fields (`chosen_path_id`,
  `last_seen_at`, `completed_concepts`) are deliberately NOT exposed yet — the task scoped the
  change to declared skills only.
- **Ranking isolation is a tested contract.** `declared_skills` is stored on the profile but
  `paths_service.build_ranked_paths` never reads it; `test_declared_skills_do_not_change_ranked_paths`
  compares the full `GET /profiles/{id}/paths` response before and after the PUT and requires
  byte-identical output.
- **Atomicity via validate-then-mutate.** Vocabulary validation runs before any attribute
  assignment; SQLite single-file transactions make the commit all-or-nothing, so the
  “writes nothing on 422” behavior is test-enforced rather than assumed.
- **Tests: backend `tests/integration/test_skills_api.py` (10 tests covering the full required
  list) + frontend `SkillPicker.test.tsx` (8 tests covering loading/error/retry, alias search,
  chips/count, pre-fill, exact save payload + confirmation, 422 message with selection kept,
  keyboard operation).**

### Known limits (Phase 4 carry-over)

- The picker is purely declarative today: nothing computed (Phase 6 gap analysis) consumes it
  yet, per “do not touch Phase 5/6 work”.
- `GET /skills` has no pagination/filter params — the whole 53-skill vocabulary is served;
  that is intentional at this vocabulary size.

---

## Phase 5 — Opportunity tracker

### What was added

**Backend**

- **Endpoints** (`app/api/v1/profiles.py`, thin):
  - `PUT /profiles/{id}/chosen-path` body `{path_id}`: valid path → 200; unknown path →
    422 `invalid_path`; re-PUT switches the tracked path.
  - `POST /profiles/{id}/seen`: sets `last_seen_at = clock.now()` (injectable via
    `app/core/clock.py`, naive UTC everywhere).
  - `GET /profiles/{id}/opportunities?internship=&region=&limit=&offset=`: never writes
    `last_seen_at`; no chosen path → 409 `path_required`; no assessment → 409
    `assessment_required`; unknown profile → 404.
- **New errors** (`app/core/errors.py`): `InvalidPathError` (422), `PathRequiredError` (409).
- **Services:**
  - `services/match_service.py` — pure `posting_match`: `match = 100 × (0.6 × skill_overlap
    + 0.4 × readiness_n)` with named constants `W_SKILL_OVERLAP = 0.6`, `W_READINESS = 0.4`;
    `None` when the posting has no extracted skills.
  - `services/tracker_service.py` — chosen-path PUT, POST /seen (injectable clock),
    `list_opportunities` (read-only feed: both core and extended tiers, strict `is_new`,
    ordering match desc → nulls last → first_seen_at desc → posting id, total independent
    of paging, `first_visit`, `last_refreshed_at` = latest successful jobs `refresh_runs`
    `finished_at`), and `get_trend` + `get_refresh_status`.
- **Scheduler** (`app/scheduler/jobs.py`, `app/main.py` lifespan): `BackgroundScheduler`
  created **only when `SCHEDULER_ENABLED=true`** (default false), with three cron jobs read
  from env (`JOBS_DAILY_CRON`, `JOBS_INDIA_WEEKLY_CRON`, `SCHOLAR_WEEKLY_CRON`) — no hardcoded
  cron strings. Each job opens its own DB session (context-manager session factory), catches
  every exception into a failed `refresh_runs` row with a scrubbed error text (repr, truncated,
  never the request URL), stops cleanly at the SerpApi daily cap, and uses `max_instances=1`,
  `coalesce=True`; the scheduler shuts down at app exit.
- **Pulse snapshots:** after every jobs refresh, one `pulse_snapshots` row is upserted per
  (subfield, UTC date, region) with `active_postings`, `new_postings` (postings whose
  `first_seen_at` falls on that date), `internship_postings`; unique on (subfield, date,
  region) so re-runs update, never duplicate. No synthetic rows.
- **Read endpoints:** `GET /pulse/{subfield_id}/trend?region=` (date-ascending
  `[{date, active, new, internships}]`; 404 unknown subfield; `[]` with no data) and
  `GET /meta/refresh-status` (last run per kind `jobs` / `scholar` / `extraction`; null for
  kinds that never ran; error text contains no key or token).
- **Schemas:** `app/schemas/opportunities.py` (`ChosenPathIn/Out`, `SeenOut`,
  `OpportunityItem`, `OpportunitiesOut`), `TrendPoint` (pulse), `RefreshStatus*` (meta);
  `ProfileOut` gained `chosen_path_id`.
- **Tests:** `tests/unit/test_match_service.py` (tests 1–7, table-driven) and
  `tests/integration/test_opportunities_api.py` (tests 8–25),
  `tests/integration/test_scheduler.py` (tests 26–33).

**Frontend**

- **Feature `src/features/tracker/`**: `api.ts` (`putChosenPath`, `postSeen`,
  `getOpportunities` — all through `lib/apiClient.ts`), `hooks/useTracker.ts` (`useChosenPath`,
  `useSetChosenPath`, `useOpportunities`, `useMarkSeen`, `useTrend`), and components:
  - `TrackPathButton` — “Track this path” / “Tracking ✓” / “Switch to this path”; switching
    is allowed; mounted on every `PathCard`.
  - `OpportunityCard` — match badge (`{n}% match` or “Not enough info” for null), NEW badge
    shown only when `is_new && !first_visit`, apply link with `rel="noopener noreferrer"`.
  - `LastRefreshedPill` — relative time, or “never refreshed” when null.
  - `TrendSparkline` — inline SVG (`role="img"` + full text `aria-label`); renders only
    with ≥ 2 snapshots; 1 shows “tracking started <date>”; 0 shows “no history yet”.
- **Pages:** `/opportunities` (`OpportunitiesPage`) with region + internship filters,
  collapsible SkillPicker panel (after saving, opportunities are refetched), “Mark all as
  seen” (POST /seen → refetch → badges clear), first-visit intro note instead of badges,
  and loading/empty/error states; 409 `path_required` redirects to `/paths` with a banner.
- **AppShell:** the “Opportunities” nav item is enabled only once a path is tracked
  (reads the profile via `useChosenPath`); a non-clickable hint renders otherwise.
- **Types:** `types/api.ts` mirrors the new backend schemas tracker-section.
- **Tests:** 23 new frontend tests (`TrackerComponents.test.tsx`, `TrackerGating.test.tsx`,
  `OpportunitiesPage.test.tsx`) — TrackPathButton PUT + switch, nav gate, NEW-badge gating,
  mark-as-seen clears badges, match badge, filters change request params, LastRefreshedPill,
  sparkline states + text alternative, loading/empty/error.

### Data flow

```
PathsPage ──TrackPathButton──▶ PUT /profiles/{id}/chosen-path ─▶ profile.chosen_path_id
AppShell ──useChosenPath──▶ profile.chosen_path_id ≠ null ⇒ enable nav “Opportunities”

GET /profiles/{id}/opportunities (read-only; never touches last_seen_at)
  ├─ tracker_service.list_opportunities(db, profile, region, internship, limit, offset)
  │    ├─ guard: chosen_path_id (409 path_required), latest assessment (409 assessment_required)
  │    ├─ active postings of the path's subfield in the region, both tiers
  │    ├─ match_service.posting_match(posting_skills, declared_skills, readiness_n)
  │    │    match = 100 × (0.6×overlap + 0.4×readiness_n); None when no extracted skills
  │    ├─ is_new = first_seen_at > last_seen_at (strict); null last_seen ⇒ all new + first_visit
  │    └─ sort: match desc (nulls last) → first_seen_at desc → posting_id
  └─ last_refreshed_at = max successful jobs refresh_runs.finished_at
“Mark all as seen” ─▶ POST /profiles/{id}/seen ─▶ profile.last_seen_at = now (clock)

Scheduler (SCHEDULER_ENABLED=true only)
  cron jobs ─▶ own session ─▶ ingestion/extraction/research services
     ├─ SerpApi daily cap respected; failure → failed refresh_runs row (scrubbed)
     └─ after jobs refresh: upsert pulse_snapshots per (subfield, UTC date, region)
GET /pulse/{id}/trend ─▶ snapshot series date-asc ─▶ TrendSparkline (≥ 2 points)
GET /meta/refresh-status ─▶ last run per kind ─▶ status/admin UI
```

### Decision log (Phase 5)

- **Match readiness input:** the data model has no posting-level scored primary-subfield
  column, so readiness_n comes from the tracked path's subfield (plan Section 4.5 fallback
  branch). Recorded per the phase instructions; a `primary_subfield_id` extraction column
  would let future phases use the per-posting subfield instead.
- **Naive UTC everywhere** (`app/core/clock.py`): one convention across services, models and
  tests; SQLite round-trip comparisons are covered by a dedicated test (test 21).
- **GET opportunities is strictly read-only:** the frontend explicitly POSTs `/seen` when the
  user views the list, so a page refresh cannot silently clear NEW badges.
- **NEW badges gated on `!first_visit`:** on a first visit `last_seen_at` is null and every
  row qualifies as new; the UI shows an intro note instead of shouting NEW on everything.
- **`is_new` is strict:** `first_seen_at == last_seen_at` is NOT new; the equal-timestamp
  behavior is a test-enforced contract (test 8).
- **Snapshots upsert, never duplicate:** unique (subfield, date, region) with an upsert;
  re-running the same day updates the row (test 22). No synthetic history — Phase 7 owns
  demo data.
- **Scheduler stays OFF by default:** `SCHEDULER_ENABLED=false`; all scheduler tests toggle
  the flag explicitly. Jobs stop at the daily cap instead of crashing, and failed runs land
  in `refresh_runs` for `GET /meta/refresh-status`.
- **Injectable clock, no time library:** tests pass a controlled clock; no `freezegun` or
  other dependency was added (approved-stack rule).
- **`useTrend` query per pulse card:** the sparkline fetches
  `/pulse/{subfield_id}/trend?region=` with a 5-minute staleTime; a missing QueryClient
  (standalone component tests) degrades to the “no history yet” state instead of crashing.

### Known limits (Phase 5)

- The scheduler keeps data fresh only while the backend runs and `SCHEDULER_ENABLED=true`;
  during development it is off and refreshes happen via the admin endpoints.
- `last_refreshed_at` reflects the latest successful **jobs** refresh only (scholar/extraction
  runs are visible via `/meta/refresh-status`, not on the pill).
- Opportunities pagination uses limit/offset (default limit 50) but the UI exposes no pager
  yet; the total is shown so Phase 7 can add one if needed.
- The sparkline plots `active` only; `new` and `internships` are in the endpoint response and
  the accessible text alternative but not drawn.
- Pulse-card sparklines issue one trend query per card (6 on the Pulse page); acceptable at
  this scale, batched only if it matters.

### Flag derivation fix (post-Phase-5, M-10 follow-up)

- `services/flag_rules.py`: pure, unit-tested evidence rules. A Gemini
  seniority claim is persisted **only** when the claimed bucket's keyword
  appears in the title or the first 3,000 description chars; a claim is never
  remapped to another bucket; "Scientist"/"Engineer" are never seniority
  evidence. `faculty` was added to the `Seniority` Literal
  (`integrations/gemini/schemas.py`) and the frontend label map (`MixChips`).
- `requires_phd` is fully text-derived: True = required-PhD wording or an
  explicit PhD-student/postdoc role; False = explicit "no PhD" wording;
  "preferred" and silence → NULL. The model's boolean claim is no longer read.
- `is_internship` reverts to title+extensions rule only
  (`parsers.detect_internship`); the old model-OR is gone because the model
  could flag regular jobs as internships. An internship forces
  `seniority="intern"`.
- These evidence rules were prompted by the M-10 spot check (model flags wrong
  in 15/20 sampled postings); existing tests that asserted model-verbatim
  persistence were updated to supply keyword evidence instead of loosening
  assertions. Previously extracted DB rows are unaffected until re-extraction
  (skills links are replaced, not appended, on any re-run).
