"""Pulse read endpoints.

Endpoints: ``GET /pulse``, ``GET /pulse/{subfield_id}`` and
``GET /pulse/{subfield_id}/postings``.
Thin routers per AGENTS.md 3.3.1.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.pulse import (
    PostingListResponse,
    PostingOut,
    PulseCard,
    SubfieldDetail,
    TrendPoint,
)
from app.services import pulse_service, tracker_service

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
    "/pulse/{subfield_id}",
    response_model=SubfieldDetail,
    summary="Subfield detail: skills, themes, mix, coverage, postings",
)
def get_subfield_detail(
    subfield_id: str,
    region: str = Query(default="global", pattern="^(global|india)$"),
    db: Session = Depends(get_db),
) -> SubfieldDetail:
    """Return the full intelligence detail for one subfield.

    Args:
        subfield_id: subfield to detail (404 when unknown).
        region: ``global`` or ``india``.
        db: request session.

    Returns:
        SubfieldDetail with card fields plus top_skills, seniority_mix,
        phd_share, extraction_coverage, themes with papers, and postings.
    """
    detail = pulse_service.get_subfield_detail(db, subfield_id, region)
    return SubfieldDetail.model_validate(detail)


@router.get(
    "/pulse/{subfield_id}/trend",
    response_model=list[TrendPoint],
    summary="Daily snapshot series for a subfield",
)
def get_trend(
    subfield_id: str,
    region: str = Query(default="global", pattern="^(global|india)$"),
    db: Session = Depends(get_db),
) -> list[TrendPoint]:
    """Return the subfield's snapshot series, date ascending (plan 5.4).

    Args:
        subfield_id: taxonomy id (404 when unknown).
        region: region to filter on (default global).
        db: request session.

    Returns:
        [{date, active, new, internships}] oldest-first; [] if no data yet.

    Raises:
        NotFoundError: unknown subfield (404).
    """
    points = tracker_service.get_trend(db, subfield_id, region=region)
    return [TrendPoint.model_validate(point) for point in points]


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
