"""Gemini prompt constants (plan 4.7) — every LLM instruction lives here.

Rules for every prompt (AGENTS 3.5.6): state that ONLY supplied data may be
used, forbid invented numbers/URLs, and demand null/absence when something is
unknown. Templates use ``str.format``-style placeholders filled by the services
(``extraction_service``, ``research_service``); the text outside the
placeholders is exactly the plan 4.7 wording.
"""

from __future__ import annotations

SKILL_EXTRACTION_PROMPT = """\
You extract structured data from quantum-industry job postings.
Rules:
- Use ONLY skill ids from the provided VOCABULARY. If a posting names a skill that is not in
  the vocabulary, put its plain-text name in unmapped_skills. Never invent ids.
- Do not guess. If the posting does not state seniority or a PhD requirement, return null/"unknown".
- primary_subfield_id must be one of the listed subfield ids, or null.
Return one item per input posting, in the same order, echoing posting_ref.
VOCABULARY:
{vocabulary}
SUBFIELDS:
{subfields}
POSTINGS:
{postings}
"""

RESEARCH_THEMES_PROMPT = """\
Using ONLY the papers listed (titles and snippets), identify 3 to 5 distinct research themes.
For each: a label (max 6 words), a one-sentence summary (max 30 words), and the paper indexes
that support it. Do not use outside knowledge. Do not claim growth or trends; describe what
these recent papers are about.
PAPERS:
{papers}
"""

#: Path explanations (plan 4.7): the model only ever sees the backend-computed
#: evidence JSON and must copy numbers verbatim — the server-side validator
#: (explanation_service) rejects any number that is not in that JSON.
PATH_EXPLANATIONS_PROMPT = """\
You write short, honest career-fit explanations for six quantum career paths.
Use ONLY the numbers and items in the provided JSON. Do not invent statistics, salaries,
company claims or URLs. Copy every number exactly as it appears in the JSON — never round,
convert to a different unit, or introduce a number that is not present. If a path has
low_data true, say that the demand evidence is thin. If saturated is true, note that
sampling compresses demand differences.
Output one item per path, echoing its path_id. For each item: headline (max 12 words);
reasons (exactly 3, each max 25 words, each tied to a provided number); caveat (max 30
words); next_step (max 25 words).
PATHS:
{paths}
"""
