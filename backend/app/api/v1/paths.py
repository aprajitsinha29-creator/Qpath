"""Paths endpoints for career path recommendations (plan 4.5).

Thin routers per AGENTS.md 3.3.1: parse input, call the service, return the
schema. Scoring and LLM orchestration happen inside paths_service and
explanation_service — never here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_structured_llm_optional
from app.db.session import get_db
from app.schemas.paths import PathExplanationOut, PathsOut
from app.services import paths_service

if TYPE_CHECKING:
    from app.integrations.gemini.client import StructuredLLM

router = APIRouter(prefix="/profiles/{profile_id}/paths", tags=["paths"])


@router.get("", response_model=PathsOut, summary="Get ranked paths with cached explanations")
def get_paths(
    profile_id: str,
    region: Literal["global", "india"] = Query("global", description="Demand and evidence region"),
    db: Session = Depends(get_db),
) -> PathsOut:
    """Return all six ranked career paths for a profile's latest assessment.

    Attaches only CACHED explanations — never calls Gemini, so it works with no
    key and no quota.

    Args:
        profile_id: UUID path parameter.
        region: global or india.
        db: request session.

    Returns:
        PathsOut containing six ranked PathResult objects.

    Raises:
        NotFoundError: unknown profile (404).
        AssessmentRequiredError: no assessment submitted yet (409).
    """
    return paths_service.get_ranked_paths(db, profile_id, region=region)


@router.post(
    "/explanations",
    response_model=PathsOut,
    summary="Generate or return cached explanations for all six paths",
)
def generate_all_explanations(
    profile_id: str,
    region: Literal["global", "india"] = Query("global", description="Demand and evidence region"),
    db: Session = Depends(get_db),
    llm: StructuredLLM | None = Depends(get_structured_llm_optional),
) -> PathsOut:
    """Generate or retrieve cached explanations for all six career paths.

    Batched endpoint: makes ONE Gemini call for any missing explanations across
    all six paths, validating numbers and falling back to deterministic templates
    on LLM errors or quota exhaustion.

    Args:
        profile_id: UUID path parameter.
        region: global or india.
        db: request session.
        llm: injected optional Gemini StructuredLLM client.

    Returns:
        PathsOut containing all six paths with their explanation fields filled.

    Raises:
        NotFoundError: unknown profile (404).
        AssessmentRequiredError: no assessment submitted yet (409).
    """
    return paths_service.get_ranked_paths_with_explanations(db, profile_id, region=region, llm=llm)


@router.post(
    "/{path_id}/explanation",
    response_model=PathExplanationOut,
    summary="Generate or return cached explanation for one path",
)
def generate_path_explanation(
    profile_id: str,
    path_id: str,
    region: Literal["global", "india"] = Query("global", description="Demand and evidence region"),
    db: Session = Depends(get_db),
    llm: StructuredLLM | None = Depends(get_structured_llm_optional),
) -> PathExplanationOut:
    """Generate or return the cached explanation for a single career path.

    Also ensures explanations for all six paths behind the scenes in ONE call,
    persisting them under their evidence hash, and returns the requested item.

    Args:
        profile_id: UUID path parameter.
        path_id: Career path ID.
        region: global or india.
        db: request session.
        llm: injected optional Gemini StructuredLLM client.

    Returns:
        PathExplanationOut for the requested path.

    Raises:
        NotFoundError: unknown profile or unknown path_id (404).
        AssessmentRequiredError: no assessment submitted yet (409).
    """
    return paths_service.request_explanation(db, profile_id, path_id, region=region, llm=llm)
