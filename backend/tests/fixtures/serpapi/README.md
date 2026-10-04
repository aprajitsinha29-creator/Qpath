# Recorded SerpApi fixtures

Real responses recorded by `make record-fixtures` (see `backend/scripts/record_fixtures.py`).

- Naming: `<engine>__<slugified query>__<variant>.json`, e.g.
  `google_jobs__quantum-error-correction__global_p1.json`.
- Variants: jobs use `global_p1`, `global_p2`, `india_p1`; scholar uses `recent`.
- **No API keys.** Every file is scrubbed of `api_key` before saving; a test
  (`test_fixtures_contain_no_api_key`, Phase 0 step 0.8) enforces this once
  fixtures are recorded.
- These files are committed on purpose: they let the whole app and test suite
  run offline in fixture mode without spending SerpApi credits.
