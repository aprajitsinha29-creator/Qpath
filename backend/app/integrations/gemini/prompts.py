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
