"""Declarative SQLAlchemy Base for every ORM model (SQLAlchemy 2.0 style)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Marker base class; models register on ``Base.metadata`` via inheritance."""
