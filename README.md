# Quantum Pathfinder

> A live-data career navigator for quantum computing: it measures what you know (an 18-question diagnostic), reads the quantum job market and recent research (SerpApi Google Jobs and Google Scholar), recommends career paths with deterministic scoring, and then keeps tracking matched opportunities for the path you choose.

Built for the **SerpApi India Hackathon 2026**.

---

## What it is

Quantum Pathfinder is a live-data career navigator for quantum computing: it measures what you know (an 18-question diagnostic), reads the quantum job market and recent research (SerpApi Google Jobs and Google Scholar), recommends career paths with deterministic scoring, and then keeps tracking matched opportunities for the path you choose.

## Quick start

```bash
git clone https://github.com/aprajitsinha29-creator/Qpath.git
cd Qpath
python setup_project.py
```

Then edit `backend/.env` to add your API keys (optional for offline fixture mode).

Finally, start the app:

```bash
python setup_project.py --start
```

Open `http://localhost:5173` in your browser.

**Fixture mode :** with `SERPAPI_USE_FIXTURES=true` (the default in `backend/.env.example`) the app runs entirely offline against recorded real SerpApi responses in `backend/tests/fixtures/serpapi/` — no API key and no credits needed for the backend itself. The Gemini-backed features (skill extraction, research themes, path explanations) additionally need `GEMINI_API_KEY`/`GEMINI_MODEL`; leave them empty and those views fall back to labelled templates or show empty states. Copy `backend/.env.example` → `backend/.env` and `frontend/.env.example` → `frontend/.env` first.

## Features as built

- **Orientation diagnostic** — an 18-question quiz (one per screen, interests first, review before submit). Scoring is deterministic: points earned over points available per subfield, difficulty 1-3 worth 1-3 points; "Not sure" scores 0 and there is no negative marking. Results show a readiness radar plus a per-concept feedback list.
- **Six career paths** — every path is scored `0.40 × interest + 0.30 × demand + 0.30 × readiness` (log-compressed demand, named constants in the code), ranked server-side, and shown with a score breakdown, evidence panel (posting counts, PhD share, top skills, sample postings) and an honest AI explanation labelled either "AI-generated from the data shown" or "Template fallback (deterministic)". Declaring skills never changes path scores.
- **Opportunity tracker** — pick a path, then a feed of matched postings with a match badge (`0.6 × skill overlap + 0.4 × readiness`; "Not enough info" when the posting has no extracted skills), region and internship filters, a NEW badge for postings first seen after you last pressed "Mark all as seen", and a trend sparkline on pulse cards (drawn only once at least two days of snapshots exist).
- **Method page** — the verbatim contents of `docs/DATA_AND_METHOD.md` (sources, formulas, accuracy checks, known limits) plus a live-numbers block read from the backend (SerpApi calls per engine, posting totals, extraction coverage, last refresh times).

## Data sources

- **Google Jobs via SerpApi** — postings per subfield. Each of the six subfields has one *core* search (used for headline counts and demand) and up to three *extended* searches (excluded from headline counts so a subfield with more searches does not look bigger). Postings are de-duplicated by title, company and location.
- **Google Scholar via SerpApi** — one search per subfield, sorted by date, about 20 recent papers each, used only to extract qualitative research themes. Scholar's result totals are erratic, so the app never computes a trend or growth rate from them.
- **Daily call cap** — live calls are limited by `SERPAPI_DAILY_CALL_CAP` per UTC day; the cap is counted from the call log and exceeded calls raise an error instead of silently running over.
- **Call log** — every SerpApi call (live or fixture) is written to the `serpapi_call_log` table with engine, query, source and status; the Method page's live-numbers block and the UI's SerpApi activity panel read from it.

## Limits

- Posting counts are a **sample, not a census**: Google Jobs returns a limited number of pages per search, and busy subfields hit that cap (flagged as saturated).
- **The India view is thin** and indicative only.
- **Duplicates and non-quantum leakage**: the same job listed in several locations can appear more than once, and postings leak in when a company name contains the word (for example QuantumBlack, an AI consultancy); some results are academic faculty searches, policy roles or hardware assembly roles. All of these inflate counts a little.
- **Quiz answers are unverified beyond their drafting**: 18 questions drafted with LLM assistance, reviewed one by one by the author, and cross-checked by answering them without the key in a second model (DeepSeek); all 18 answers matched the key. There was **no external expert review**, and not every citation was checked against its source.
- The app is a decision aid. It makes no claim about hiring odds or salary.
- Free-tier Gemini quotas are small, so explanations may fall back to templates.

## Environment variables

Backend (`backend/.env`, copy `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Runtime environment name (shown in `/health`) |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `DATABASE_URL` | `sqlite:///./data/pathfinder.db` | SQLite path (`backend/data/` is gitignored) |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed origins for browser requests |
| `ADMIN_TOKEN` | `change-me` | Token for `X-Admin-Token` on admin endpoints |
| `SERPAPI_API_KEY` | *(empty)* | SerpApi key — only needed when `SERPAPI_USE_FIXTURES=false` |
| `SERPAPI_USE_FIXTURES` | `true` | `true` = read recorded JSON, spend no credits |
| `SERPAPI_DAILY_CALL_CAP` | `60` | Hard stop for live calls per UTC day |
| `SERPAPI_JOBS_MAX_PAGES` | `3` | Max pages per query in bootstrap mode |
| `GEMINI_API_KEY` | *(empty)* | Gemini API key (extraction, themes, explanations) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model id |
| `GEMINI_REQUESTS_PER_MINUTE` | `5` | Client-side rate limit |
| `SCHEDULER_ENABLED` | `false` | Keep off during development (refreshes via admin endpoints) |
| `JOBS_DAILY_CRON` | `0 3 * * *` | Daily job refresh (only when `SCHEDULER_ENABLED=true`) |
| `JOBS_INDIA_WEEKLY_CRON` | `0 4 * * 1` | Weekly job refresh (same gate) |
| `SCHOLAR_WEEKLY_CRON` | `0 5 * * 1` | Weekly Scholar refresh (same gate) |
| `ALLOW_UNVERIFIED_QUESTIONS` | `true` | The example ships `true` while quiz answers await sign-off; set `false` for evaluation |
| `DEMO_MODE` | `false` | Serve labelled demo history |

Frontend (`frontend/.env`, copy `frontend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | FastAPI base URL used by `lib/apiClient.ts` |

`backend/.env` is gitignored and must never be committed. With `SERPAPI_USE_FIXTURES=true` the whole app and test suite run with no API keys.

## Status

| Phase | Description | Status |
|---|---|---|
| **0** | Foundation: FastAPI backend, health endpoint, SerpApi client in fixture mode, frontend shell | ✅ Done |
| **1** | Market Pulse: six subfield cards, active-posting counts, de-duplication | ✅ Done |
| **2** | Intelligence layer: Gemini skill extraction + Scholar research themes, pulse detail pages | ✅ Done |
| **3** | Orientation diagnostic: 18-question quiz, readiness scoring, per-concept feedback | ✅ Done |
| **4** | Path matcher: deterministic ranked career paths with grounded explanations, declared-skills picker | ✅ Done |
| **5** | Opportunity tracker: chosen path, seen state, opportunity feed with match scores and NEW badges, trend sparklines, refresh status | ✅ Done |
| **6** | (section 6 of the build plan — not built) | — Not built |
| 7 | Submission hardening | — Not built |

## AI tools used

- **Google Gemini** (`google-genai` SDK, structured output) is the only LLM integrated in the app, for three jobs: extracting skills/seniority/PhD/internship flags from posting text against a fixed 53-skill vocabulary; proposing 3-5 research themes from supplied Scholar titles and snippets; and writing path explanations from supplied evidence only — it never produces a score or a ranking, every output is schema-validated, and a deterministic template is shown (labelled as a template) when the model output is unusable or the quota is gone.
- **An LLM coding agent (Codebuff, GLM)** assisted with writing and refactoring the code, the test suites and this documentation; all behavioural logic is reviewed and owned by the author.
- **DeepSeek** was used once, as a cross-check of the quiz key: the 18 questions were answered again without the key in DeepSeek and all 18 answers matched (author review is the primary verification; there was no external expert review).
- SerpApi Google Jobs and Google Scholar supplied all market and research data; no other dataset is used.

## Development commands

```bash
make setup   # one-time setup
make dev-backend
make dev-frontend
make test    # backend pytest + frontend vitest (offline, fixture mode)
make lint    # ruff + eslint + prettier
```
