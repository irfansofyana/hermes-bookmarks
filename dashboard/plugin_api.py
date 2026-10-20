"""Read-only preview API. Authentication is supplied by the real Hermes host.

This module is imported by file path, not as a child of the agent package.
Do not add a second context singleton, auth system, or per-profile data root.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def get_health() -> dict:
    """Package liveness only, not library readiness or host compatibility."""
    return {
        "ok": True,
        "plugin": "hermes-bookmarks",
        "stage": "foundation_preview",
        "library_ready": False,
    }
