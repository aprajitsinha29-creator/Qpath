"""Pydantic schemas for Gemini structured output (plan 4.7).

These are the **LLM-facing** contracts: each model is passed to the google-genai
SDK as ``response_schema`` (paired with ``response_mime_type="application/json"``,
AGENTS 3.5.2) and every response is re-validated against it before use. They are
internal integration schemas — deliberately separate from ``app/schemas/``
(API response models) so the LLM contract can evolve without touching the API.

Nothing here is trusted without validation: the client re-parses raw text with
these models, and the services run domain checks on top (vocabulary ids, paper
index ranges, list-length matching) because a schema-valid response can still
be domain-invalid (AGENTS 3.5.3).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: Allowed seniority buckets. ``unknown`` is a *value the model may return*
#: when the posting does not state seniority; it is stored as NULL in the DB
#: so "unknown" stays distinguishable from "extracted but negative" (plan 4.3).
Seniority = Literal[
    "intern",
    "entry",
    "mid",
    "senior",
    "lead",
    "postdoc",
    "phd_student",
    "faculty",
    "unknown",
]


class PostingExtraction(BaseModel):
    """Structured facts extracted from ONE posting.

    Attributes:
        posting_ref: echo of the caller-supplied reference (the posting id) —
            used to match outputs back to inputs in order.
        skill_ids: vocabulary skill ids mentioned by the posting. Ids outside
            the supplied vocabulary are dropped to ``unmapped_skills`` by the
            service's post-validation — the model is told never to invent ids,
            but the DB is protected regardless (plan 4.7).
        unmapped_skills: plain-text skill names that matched no vocabulary id.
        seniority: stated or implied seniority, or ``unknown``.
        requires_phd: True/False only when the posting states or clearly implies
            it, else None ("do not guess" — prompt rule).
        is_internship: the model's read; OR-ed with the rule-based detection at
            persistence time, so it can only ever *add* internships (plan 4.7).
        primary_subfield_id: one of the supplied subfield ids, or None.
    """

    posting_ref: str
    skill_ids: list[str] = Field(default_factory=list)
    unmapped_skills: list[str] = Field(default_factory=list)
    seniority: Seniority = "unknown"
    requires_phd: bool | None = None
    is_internship: bool = False
    primary_subfield_id: str | None = None


class ExtractionBatch(BaseModel):
    """One batch response: exactly one item per input posting, same order."""

    items: list[PostingExtraction] = Field(default_factory=list)


class Theme(BaseModel):
    """One qualitative research theme drawn from a batch of recent papers.

    Attributes:
        label: short theme name (max 6 words per the prompt).
        summary: one-sentence description (max 30 words per the prompt).
        paper_indexes: 1-based indexes into the supplied paper list — the only
            evidence pointers the model may use (no URLs, no invented papers).
    """

    label: str
    summary: str
    paper_indexes: list[int] = Field(default_factory=list)


class ThemeSet(BaseModel):
    """Theme generation response: 3–5 themes over the supplied papers."""

    themes: list[Theme] = Field(default_factory=list)


class PathExplanationItem(BaseModel):
    """One path's grounded explanation as written by the model (plan 4.7).

    Field limits are deliberately LOOSE here: word counts, the exactly-3
    reasons rule and the numbers-in-evidence check are per-item domain
    validations in ``explanation_service`` so one bad item falls back to its
    template without discarding the other five (design decision 1). A strict
    schema would make the google-genai client reject the whole batch.
    """

    path_id: str = ""
    headline: str = ""
    reasons: list[str] = Field(default_factory=list)
    caveat: str = ""
    next_step: str = ""


class PathExplanationsBatch(BaseModel):
    """ONE Gemini call returns explanations for all six paths (design decision 1).

    The Gemini quota is tiny: a batch of six per assessment is one request,
    and each item is validated — or templated — independently.
    """

    explanations: list[PathExplanationItem] = Field(default_factory=list)
