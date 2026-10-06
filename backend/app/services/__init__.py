"""Business-logic layer: routers call services; services never import HTTP types.

Modules are imported by path (``from app.services import extraction_service``);
this package re-exports nothing itself so import order never creates cycles.
"""
