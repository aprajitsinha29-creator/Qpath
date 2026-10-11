"""Evidence-based posting flag derivation (pure functions, Phase 2 hardening).

Fix for the extraction spot-check (M-10): the model's seniority/PhD/internship
claims were stored verbatim and were wrong in 15/20 sampled postings. These
pure functions gate EVERY model claim against keyword evidence in the posting
text itself, so the DB only ever holds flags a human can verify by reading the
same text (AGENTS 3.3.10: scoring/labels are deterministic code, the LLM never
decides a fact shown in the UI).

Scope decisions (recorded also in ARCHITECTURE.md):
- ``seniority``: a model value survives ONLY if the title or the first 3,000
  description characters contain a keyword for that exact bucket. Role words
  like "Scientist"/"Engineer" are deliberately NOT keywords — they say nothing
  about seniority. ``faculty`` exists as a bucket (professor/lecturer titles
  are common in quantum research hiring).
- ``requires_phd`` is fully text-derived: True only for required-PhD wording
  or explicitly PhD-student/postdoc roles, False only for explicit "no PhD"
  wording, ``"preferred"`` and no evidence are both None (never guess).
- ``is_internship`` is rule-based from title + extensions ONLY (reuses the
  ingestion regex via ``parsers.detect_internship``) — the model can no longer
  turn a regular job into an internship. Internship implies seniority
  ``intern``; the reverse is not enforced (an "interns wanted" note in a body
  keeps seniority=intern with internship rule False from the title alone).

No imports from FastAPI, SQLAlchemy or Gemini here: this module must stay
unit-testable without a database or network.
"""

from __future__ import annotations

import re

from app.integrations.serpapi.parsers import detect_internship

#: Evidence window: description characters that may support a keyword match,
#: identical to the truncation used before text enters the LLM prompt
#: (extraction_service.DESCRIPTION_TRUNCATE_CHARS) — so what the model saw is
#: exactly the evidence we re-check.
EVIDENCE_DESCRIPTION_CHARS = 3000

#: Allowed seniority buckets, mirroring the Gemini schema Literal (keep the
#: two lists identical; the schema enforces the model side, this the DB side).
SENIORITY_BUCKETS: frozenset[str] = frozenset(
    {"intern", "entry", "mid", "senior", "lead", "postdoc", "phd_student", "faculty"}
)

#: Keyword patterns per bucket (case-insensitive). Only word-shaped matches
#: count, so "mislead"/"staffing" cannot skip into lead/staff. ``sr.`` requires
#: the dot because bare "sr" is not a real-world seniority marker.
SENIORITY_KEYWORDS: dict[str, tuple[re.Pattern[str], ...]] = {
    "intern": (re.compile(r"\bintern(ship)?s?\b", re.IGNORECASE),),
    "entry": (
        re.compile(r"\bentry[- ]level\b", re.IGNORECASE),
        re.compile(r"\bjunior\b", re.IGNORECASE),
        re.compile(r"\bassociate\b", re.IGNORECASE),
        re.compile(r"\bnew\s+grad\b", re.IGNORECASE),
    ),
    "mid": (re.compile(r"\bmid[- ]level\b", re.IGNORECASE),),
    "senior": (
        re.compile(r"\bsenior\b", re.IGNORECASE),
        # "sr." needs the dot but NOT a trailing \b: no boundary exists between
        # the dot and a following space, and \bsr\b alone would match inside
        # "Story"-like words through wrong casing anyway.
        re.compile(r"\bsr\.", re.IGNORECASE),
        re.compile(r"\bstaff\b", re.IGNORECASE),
        re.compile(r"\bprincipal\b", re.IGNORECASE),
    ),
    "lead": (
        re.compile(r"\blead\b", re.IGNORECASE),
        re.compile(r"\bdirector\b", re.IGNORECASE),
        re.compile(r"\bhead\s+of\b", re.IGNORECASE),
        re.compile(r"\bmanager\b", re.IGNORECASE),
    ),
    "postdoc": (re.compile(r"\bpostdoc(toral)?s?\b", re.IGNORECASE),),
    "phd_student": (
        re.compile(r"\bphd\s+students?\b", re.IGNORECASE),
        re.compile(r"\bdoctoral\s+students?\b", re.IGNORECASE),
        re.compile(r"\bphd\s+candidates?\b", re.IGNORECASE),
    ),
    "faculty": (
        re.compile(r"\bprofessor(s)?\b", re.IGNORECASE),
        re.compile(r"\bfaculty\b", re.IGNORECASE),
        re.compile(r"\blecturer(s)?\b", re.IGNORECASE),
    ),
}


def evidence_text(title: str | None, description: str | None) -> str:
    """Return the searchable evidence string: title plus truncated description.

    Args:
        title: posting title (may be None for defensive callers).
        description: posting description (may be None).

    Returns:
        ``title + "\\n" + description[:EVIDENCE_DESCRIPTION_CHARS]`` — the title
        always counts (ASAP rule: "the title or the first 3000 characters").
    """
    truncated = (description or "")[:EVIDENCE_DESCRIPTION_CHARS]
    return f"{title or ''}\n{truncated}"


def find_seniority_evidence(text: str) -> set[str]:
    """Return every seniority bucket whose keyword appears in ``text``.

    Args:
        text: lower/mixed-case posting text (title + truncated description).

    Returns:
        A set of bucket names from :data:`SENIORITY_BUCKETS`; empty when no
        keyword matched.
    """
    return {
        bucket
        for bucket, patterns in SENIORITY_KEYWORDS.items()
        if any(pattern.search(text) for pattern in patterns)
    }


def derive_seniority(
    title: str | None, description: str | None, model_seniority: str | None
) -> str | None:
    """Keep a model seniority claim only when the posting text corroborates it.

    Args:
        title: posting title.
        description: posting description (only the first
            :data:`EVIDENCE_DESCRIPTION_CHARS` characters are searched).
        model_seniority: the model's claim — a bucket name or its "unknown"
            sentinel; both None and ``"unknown"`` mean "not stated".

    Returns:
        The bucket name (e.g. ``"faculty"``) when the claimed bucket's keyword
        appears in the evidence text, else None. A claim is never remapped to
        a different bucket and role words like "Scientist"/"Engineer" are
        never treated as seniority evidence.

    Examples:
        "Senior Research Scientist" + model "senior" → "senior".
        "Quantum Scientist" (no keyword) + model "senior" → None.
    """
    if not model_seniority or model_seniority == "unknown":
        return None
    if model_seniority not in SENIORITY_BUCKETS:
        # Schema validation should have caught this; drop silently-but-logged
        # values rather than persisting an out-of-contract bucket (AGENTS 3.5.3).
        return None
    if model_seniority not in find_seniority_evidence(evidence_text(title, description)):
        return None
    return model_seniority


# PhD wording patterns, ordered by intent. Negative wording wins over
# everything: "no PhD required" contains both "phd" and "required".
_NO_PHD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bno\s+(?:a\s+)?(?:phd|doctorate|doctoral)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:phd|doctorate|doctoral)\b[^.\n]{0,30}\bnot\s+(?:required|needed)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bdoes\s+not\s+require\s+(?:a\s+)?(?:phd|doctorate|doctoral)\b", re.IGNORECASE),
)
_PHD_PREFERRED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:phd|doctorate|doctoral)\b[^.\n]{0,30}\bpreferred\b", re.IGNORECASE),
    re.compile(r"\bpreferred\b[^.\n]{0,30}\b(?:phd|doctorate|doctoral)\b", re.IGNORECASE),
)
_PHD_REQUIRED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:phd|doctorate|doctoral)\b[^.\n]{0,30}\brequired\b", re.IGNORECASE),
    re.compile(r"\brequired\b[^.\n]{0,40}\b(?:phd|doctorate|doctoral)\b", re.IGNORECASE),
    re.compile(r"\brequires?\s+(?:a\s+|an\s+)?(?:phd|doctorate|doctoral)\b", re.IGNORECASE),
    re.compile(
        r"\bmust\s+(?:hold|have|possess)\s+(?:a\s+)?(?:phd|doctorate|doctoral)\b",
        re.IGNORECASE,
    ),
)
# A posting *written for* PhD students/postdocs requires one by definition.
_PHD_ROLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bpostdoc(toral)?s?\b", re.IGNORECASE),
    re.compile(r"\bphd\s+(?:students?|candidates?)\b", re.IGNORECASE),
    re.compile(r"\bdoctoral\s+students?\b", re.IGNORECASE),
)


def derive_requires_phd(title: str | None, description: str | None) -> bool | None:
    """Derive the PhD requirement from posting text, not the model flag.

    Args:
        title: posting title.
        description: posting description (evidence window as above).

    Returns:
        True for required-PhD wording or explicit PhD-student/postdoc roles;
        False only for explicit no-PhD wording; None otherwise ("preferred"
        wording and silence both stay None — never guess).

    Note:
        The model's ``requires_phd`` claim is deliberately NOT an argument:
        its claims were the bug (M-10 spot check), and "false only if the text
        says no PhD is needed" is a text rule.
    """
    text = evidence_text(title, description)
    # "Preferred" wording wins FIRST: "PhD preferred but not required" is a
    # preferred-requirement posting, not a negative one (spec: preferred → null).
    # Explict negatives then beat role-word evidence: "no PhD required" contains
    # both "phd" and "required".
    if any(pattern.search(text) for pattern in _PHD_PREFERRED_PATTERNS):
        return None
    if any(pattern.search(text) for pattern in _NO_PHD_PATTERNS):
        return False
    if any(pattern.search(text) for pattern in _PHD_REQUIRED_PATTERNS):
        return True
    if any(pattern.search(text) for pattern in _PHD_ROLE_PATTERNS):
        return True
    return None


def derive_is_internship(title: str | None, extensions: list[str]) -> bool:
    """Decide the internship flag from title + extensions only (rule-based).

    Args:
        title: posting title (may be None).
        extensions: normalized SerpApi extension strings ("Internship", ...).

    Returns:
        True only when ``\\bintern(ship)?s?\\b`` matches the title or an
        extension (never "internal"/"international", never the model flag —
        a non-intern title must never become an internship). Reuses
        :func:`parsers.detect_internship` so ingestion and extraction see the
        same rule.
    """
    return detect_internship(title, extensions)
