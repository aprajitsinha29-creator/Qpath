"""Pulse read endpoints: ``GET /pulse`` and ``GET /pulse/{subfield_id}/postings``.

Thin routers per AGENTS.md 3.3.1. The card detail route
(``GET /pulse/{subfield_id}`` with skills/themes) is deliberately absent until
Phase 2 — no placeholder, no premature contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.pulse import PostingListResponse, PostingOut, PulseCard
from app.services import pulse_service

router = APIRouter(tags=["pulse"])


@router.get("/pulse", response_model=list[PulseCard], summary="One pulse card per scored subfield")
def get_pulse(
    region: str = Query(default="global", pattern="^(global|india)$"),
    db: Session = Depends(get_db),
) -> list[PulseCard]:
    """Return the six Market Pulse cards for the requested region.

    Args:
        region: ``global`` (default) or ``india``.
        db: request session.

    Returns:
        One PulseCard per scored subfield, in taxonomy display order.
    """
    cards = pulse_service.get_pulse_cards(db, region)
    return [PulseCard.model_validate(card) for card in cards]


@router.get(
    "/pulse/{subfield_id}/postings",
    response_model=PostingListResponse,
    summary="Postings linked to a subfield",
)
def list_postings(
    subfield_id: str,
    region: str = Query(default="global", pattern="^(global|india)$"),
    internship: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PostingListResponse:
    """Return one page of postings for a subfield (both query tiers).

    Args:
        subfield_id: subfield whose postings to list (404 when unknown).
        region: ``global`` or ``india``.
        internship: optional filter — true for internships only, false to
            exclude them, omitted for everything.
        limit: page size (1–100).
        offset: pagination offset.
        db: request session.

    Returns:
        PostingListResponse — the page plus the unpaginated total.
    """
    postings, total = pulse_service.list_postings(
        db,
        subfield_id,
        region=region,
        internship=internship,
        limit=limit,
        offset=offset,
    )
    return PostingListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[PostingOut.model_validate(pulse_service.to_posting_out(p)) for p in postings],
    )
