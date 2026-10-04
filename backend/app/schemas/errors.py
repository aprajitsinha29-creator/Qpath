"""Pydantic shapes for the shared API error envelope (BUILD_PLAN 4.4)."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorBody(BaseModel):
    """Single error entry: stable snake_case code plus a human-readable message."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Every failing response in the API has exactly this shape."""

    error: ErrorBody
