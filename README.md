# QPath

> A live-data career navigator for quantum computing: it measures what you know (an 18-question diagnostic), reads the quantum job market and recent research (SerpApi Google Jobs and Google Scholar), recommends career paths with deterministic scoring, and then keeps tracking matched opportunities for the path you choose.

Built for the **SerpApi India Hackathon 2026**.

---

## What it is

QPath is a live-data career navigator for quantum computing: it measures what you know (an 18-question diagnostic), reads the quantum job market and recent research (SerpApi Google Jobs and Google Scholar), recommends career paths with deterministic scoring, and then keeps tracking matched opportunities for the path you choose.
Quantum Pathfinder helps a student or early-career person decide where to aim in quantum computing. You answer a short quiz and rate your interest in six subfields (error correction, hardware, software, algorithms, quantum machine learning, communication and networking). The app compares that with live job postings and recent research papers, ranks six career paths, explains each ranking from the evidence, and then lists matching job postings for the path you pick.

Every number and ranking comes from plain, tested functions with named constants. The AI model (Gemini) only extracts structure from text and writes explanations from supplied evidence. It never produces a score or a ranking.

## Prerequisites

- **Python 3.12 or newer**
- **Node.js 20.19 or newer** (with npm)
- **git**
- `make` is optional (Linux and macOS). It is only needed for the `make` shortcuts under [Development commands](#development-commands).

## Quick start

```bash
git clone https://github.com/aprajitsinha29-creator/Qpath.git
cd Qpath
python3 setup_project.py          # one-time setup
```

The setup script installs the backend and frontend dependencies and creates `backend/.env` and `frontend/.env` from the `.env.example` files. The defaults run the whole app offline, so you can start straight away. Edit `backend/.env` only if you want to add API keys (see [API keys](#api-keys)).

Start both servers:

```bash
python3 setup_project.py --start
```

This serves the backend at `http://localhost:8000` and the frontend at `http://localhost:5173`. Press Ctrl+C to stop.

Open `http://localhost:5173`. A fresh install has **no data yet**, so load it once:

1. Open the **Pulse** page and click **Refresh data**.
2. Paste the admin token. The default is `change-me`, which is the value of `ADMIN_TOKEN` in `backend/.env`.
3. Choose **bootstrap** and click **Run bootstrap refresh**.

In the default fixture mode this loads recorded real SerpApi responses and spends no credits. In live mode (`SERPAPI_USE_FIXTURES=false`) it calls SerpApi and counts against `SERPAPI_DAILY_CALL_CAP`.

Then take the **Diagnostic**, open **Paths** to see your ranked paths, and pick one to track.

### API keys

You do **not** need any API key to run the app. What each key adds:

| Key | Needed for | Without it |
|---|---|---|
| none (default fixture mode) | Posting counts, scoring, the quiz, path ranking, the Method page | Works fully offline on recorded data |
| `GEMINI_API_KEY` (free tier available) | Skill extraction, research themes, AI-written path explanations | Top skills and research themes stay empty, match badges say "Not enough info", and explanations show a labelled template |
| `SERPAPI_API_KEY` | Fresh live data, only when `SERPAPI_USE_FIXTURES=false` | The app uses the recorded fixtures |

Keys are your own. Put them in `backend/.env`, never in the frontend, and never commit them.

### Optional: turn on the AI features

With `GEMINI_API_KEY` and `GEMINI_MODEL` set in `backend/.env` and the backend restarted, run these once after the first refresh (replace `change-me` if you changed `ADMIN_TOKEN`):

Linux/macos:
```bash
# Extract skills, seniority and PhD flags from the stored postings
curl -X POST http://localhost:8000/api/v1/admin/extract -H "X-Admin-Token: change-me"

# Fetch recent Scholar papers and generate research themes
curl -X POST http://localhost:8000/api/v1/admin/refresh/scholar -H "X-Admin-Token: change-me"
```
Windows:
```powershell
# Extract skills, seniority and PhD flags from the stored postings
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/admin/extract" -Method Post -Headers @{ "X-Admin-Token" = "change-me" }

# Fetch recent Scholar papers and generate research themes
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/admin/refresh/scholar" -Method Post -Headers @{ "X-Admin-Token" = "change-me" }
```

Free-tier Gemini quotas are small, so extraction may need to be run again to finish.

## Features as built

- **Orientation diagnostic** — an 18-question quiz (one per screen, interests first, review before submit). Scoring is deterministic: points earned over points available per subfield, difficulty 1-3 worth 1-3 points; "Not sure" scores 0 and there is no negative marking. Results show a readiness radar plus a per-concept feedback list.
- **Market Pulse** — six subfield cards with active-posting counts, top skills, research themes, a seniority and PhD mix, an extraction-coverage caveat, and a trend sparkline that is drawn only once at least two days of snapshots exist.
- **Six career paths** — every path is scored `0.40 × interest + 0.30 × demand + 0.30 × readiness` (log-compressed demand, named constants in the code), ranked server-side, and shown with a score breakdown, an evidence panel (posting counts, PhD share, top skills, sample postings) and an honest explanation labelled either "AI-generated from the data shown" or "Template fallback (deterministic)". Declaring skills never changes path scores.
- **Opportunity tracker** — pick a path, then browse a feed of matched postings with region and internship filters, a NEW badge for postings first seen after you last pressed "Mark all as seen", and a refresh-status pill. The match badge is `0.6 × skill overlap + 0.4 × readiness`. It shows **"Not enough info"** when you have not declared any skills in the skills picker, have not taken the diagnostic, or the posting has no extracted skills. A new user therefore sees "Not enough info" until they declare skills.
- **Method page** — the verbatim contents of `docs/DATA_AND_METHOD.md` (sources, formulas, accuracy checks, known limits) plus a live-numbers block read from the backend (SerpApi calls per engine, posting totals, extraction coverage, last refresh times).

Tracking only updates when a refresh runs. The scheduler is off by default, so refresh from the Pulse page, or set `SCHEDULER_ENABLED=true` to refresh on the cron schedules below.

## Data sources

- **Google Jobs via SerpApi** — postings per subfield. Each of the six subfields has one *core* search (used for headline counts and demand) and up to three *extended* searches (excluded from headline counts so a subfield with more searches does not look bigger). Postings are de-duplicated by title, company and location.
- **Google Scholar via SerpApi** — one search per subfield, sorted by date, about 20 recent papers each, used only to extract qualitative research themes. Scholar's result totals are erratic, so the app never computes a trend or growth rate from them.
- **Daily call cap** — live calls are limited by `SERPAPI_DAILY_CALL_CAP` per UTC day. The cap is counted from the call log, and calls over the cap raise an error instead of silently running.
- **Call log** — every SerpApi call (live or fixture) is written to the `serpapi_call_log` table with engine, query, source and status. The Method page's live-numbers block and the Pulse page's SerpApi activity panel read from it.

## Limits

- Posting counts are a **sample, not a census**: Google Jobs returns a limited number of pages per search, and busy subfields hit that cap (flagged as saturated).
- **The India view is thin** and indicative only.
- **Duplicates and non-quantum leakage**: the same job listed in several locations can appear more than once, and postings leak in when a company name contains the word (for example QuantumBlack, an AI consultancy). Some results are academic faculty searches, policy roles or hardware assembly roles. All of these inflate counts a little.
- **Quiz**: all 18 questions are marked verified. Each was reviewed one by one by the author and answered again without the key in a second model (DeepSeek), where all 18 answers matched the key. There was **no external expert review**, and not every citation was checked against its source.
- **Readiness is noisy**: each subfield has only three questions and there is no negative marking, so guessing can raise a score.
- **Tracking needs a refresh** (see above); nothing updates in the background unless the scheduler is enabled.
- Free-tier Gemini quotas are small, so explanations may fall back to templates.
- The app is a decision aid. It makes no claim about hiring odds or salary.

## Environment variables

Backend (`backend/.env`, created by the setup script from `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Runtime environment name (shown in `/health`) |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `DATABASE_URL` | `sqlite:///./data/pathfinder.db` | SQLite path (`backend/data/` is gitignored) |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed origins for browser requests |
| `ADMIN_TOKEN` | `change-me` | Token for `X-Admin-Token` on admin endpoints. Change it for any shared or hosted copy |
| `SERPAPI_API_KEY` | *(empty)* | SerpApi key, only needed when `SERPAPI_USE_FIXTURES=false` |
| `SERPAPI_USE_FIXTURES` | `false` | `false` = read real time records fetched from the SerpApi call |
| `SERPAPI_DAILY_CALL_CAP` | `60` | Hard stop for live calls per UTC day |
| `SERPAPI_JOBS_MAX_PAGES` | `3` | Max pages per query in bootstrap mode |
| `GEMINI_API_KEY` | *(empty)* | Gemini API key (extraction, themes, explanations) |
| `GEMINI_MODEL` | `gemma-4-26b-a4b-it` | Gemini model id |
| `GEMINI_REQUESTS_PER_MINUTE` | `5` | Client-side rate limit |
| `SCHEDULER_ENABLED` | `false` | Background refresh. Off by default; refresh from the Pulse page instead |
| `JOBS_DAILY_CRON` | `0 3 * * *` | Daily job refresh (only when `SCHEDULER_ENABLED=true`) |
| `JOBS_INDIA_WEEKLY_CRON` | `0 4 * * 1` | Weekly India job refresh (same gate) |
| `SCHOLAR_WEEKLY_CRON` | `0 5 * * 1` | Weekly Scholar refresh (same gate) |
| `ALLOW_UNVERIFIED_QUESTIONS` | `false` | When `false`, only questions marked verified are served. All 18 are verified, so this currently changes nothing |

Frontend (`frontend/.env`, created from `frontend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | FastAPI base URL used by `lib/apiClient.ts` |

`backend/.env` is gitignored and must never be committed.

## Status

| Phase | Description | Status |
|---|---|---|
| **0** | Foundation: FastAPI backend, health endpoint, SerpApi client in fixture mode, frontend shell | ✅ Done |
| **1** | Market Pulse: six subfield cards, active-posting counts, de-duplication | ✅ Done |
| **2** | Intelligence layer: Gemini skill extraction and Scholar research themes, pulse detail pages | ✅ Done |
| **3** | Orientation diagnostic: 18-question quiz, readiness scoring, per-concept feedback | ✅ Done |
| **4** | Path matcher: deterministic ranked career paths with grounded explanations, declared-skills picker | ✅ Done |
| **5** | Opportunity tracker: chosen path, seen state, opportunity feed with match scores and NEW badges, trend sparklines, refresh status | ✅ Done |
| **6** | Gap analysis and learning plan | Not built |
| **7** | Submission hardening: Method page, data and method document, README | ✅ Done |

## AI tools used

- **Google Gemini** (`google-genai` SDK, structured output) is the only LLM integrated in the app, for three jobs: extracting skills, seniority, PhD and internship flags from posting text against a fixed 53-skill vocabulary; proposing 3-5 research themes from supplied Scholar titles and snippets; and writing path explanations from supplied evidence only. It never produces a score or a ranking, every output is schema-validated, and a deterministic template is shown (labelled as a template) when the model output is unusable or the quota is gone.
- **An LLM coding agent (Codebuff, GLM)** assisted with writing and refactoring the code, the test suites and this documentation. All behavioural logic is reviewed and owned by the author.
- **DeepSeek** was used once, as a cross-check of the quiz key: the 18 questions were answered again without the key and all 18 answers matched. Author review is the primary verification; there was no external expert review.
- SerpApi Google Jobs and Google Scholar supplied all market and research data. No other dataset is used.

## Development commands

```bash
make setup           # one-time setup (alternative to setup_project.py)
make dev-backend     # backend dev server with auto-reload
make dev-frontend    # frontend dev server
make test            # backend pytest + frontend vitest
make lint            # ruff + eslint + prettier
make format          # auto-format all code
```

Tests run offline: they use recorded fixtures and a fake LLM, and never call SerpApi or Gemini.

## Documentation

| File | Contents |
|---|---|
| `docs/DATA_AND_METHOD.md` | Sources, formulas, accuracy checks and known limits (also shown on the Method page) |
| `docs/ARCHITECTURE.md` | Layer diagram, data flows, per-phase decisions, known limits |
| `docs/BUILD_PLAN.md` | The phased build plan |
| `docs/DEMO_SCRIPT.md` | The 3-minute demo shot list |
| `AGENTS.md` | Engineering standards used throughout the build |
