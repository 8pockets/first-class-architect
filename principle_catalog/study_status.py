"""Validate private study statuses without exposing detailed study state."""

from __future__ import annotations

from typing import Any

from principle_catalog.catalog import CatalogError
from principle_catalog.models import PublicProgress


_STATUS_PROJECTION: dict[str, PublicProgress] = {
    "not_started": "unstarted",
    "learning": "learning",
    "in_progress": "learning",
    "interrupted": "learning",
    "failed": "learning",
    "reviewing": "reviewing",
    "review_due": "reviewing",
    "retest_due": "reviewing",
    "failed_retest_due": "reviewing",
    "retained_14d": "retained_14d",
    "completed_14d": "retained_14d",
}


def coarse_study_status(item: dict[str, Any]) -> PublicProgress:
    """Validate one local status and return its privacy-bounded projection."""

    status = item.get("status")
    if not isinstance(status, str) or status not in _STATUS_PROJECTION:
        raise CatalogError(f"unknown local study status: {status!r}")
    return _STATUS_PROJECTION[status]
