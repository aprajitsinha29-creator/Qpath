"""Taxonomy service: read-side assembly of the reference taxonomy (plan 1.5).

Thin aggregation over the seeded reference tables so the router stays free of
DB queries (AGENTS.md 3.3.1).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CareerPath, Concept, Subfield
from app.schemas.taxonomy import CareerPathOut, ConceptOut, SubfieldOut, TaxonomyResponse


def get_taxonomy(db: Session) -> TaxonomyResponse:
    """Return all subfields, concepts and career paths, in stable display order.

    Args:
        db: request session.

    Returns:
        TaxonomyResponse with subfields ordered by ``sort_order`` and concepts/
        paths alphabetically by id (deterministic payloads, AGENTS 3.3.10).
    """
    subfields = list(db.scalars(select(Subfield).order_by(Subfield.sort_order)))
    concepts = list(db.scalars(select(Concept).order_by(Concept.id)))
    paths = list(db.scalars(select(CareerPath).order_by(CareerPath.id)))

    return TaxonomyResponse(
        subfields=[SubfieldOut.model_validate(s) for s in subfields],
        concepts=[ConceptOut.model_validate(c) for c in concepts],
        career_paths=[CareerPathOut.model_validate(p) for p in paths],
    )
