"""Create the privacy-bounded public projection from local study state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from principle_catalog.catalog import CatalogError, load_catalog
from principle_catalog.models import PublicProgress
from principle_catalog.study import LOCAL_STUDY_STATE


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


def _coarse_status(item: dict[str, Any]) -> PublicProgress:
    status = item.get("status")
    if not isinstance(status, str) or status not in _STATUS_PROJECTION:
        raise CatalogError(f"unknown local study status: {status!r}")
    return _STATUS_PROJECTION[status]


def public_progress_from_local(
    study_state_path: Path = LOCAL_STUDY_STATE,
) -> dict[str, PublicProgress]:
    try:
        data = json.loads(study_state_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CatalogError(f"{study_state_path}: local study state not found") from error
    except json.JSONDecodeError as error:
        raise CatalogError(f"{study_state_path}: invalid JSON") from error
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise CatalogError(f"{study_state_path}: items must be a list")

    catalog_items = {item.id: item for item in load_catalog().principles}
    projected: dict[str, PublicProgress] = {}
    seen: set[str] = set()
    for raw in data["items"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            raise CatalogError(f"{study_state_path}: each item must have a string id")
        item_id = raw["id"]
        if item_id in seen:
            raise CatalogError(f"{study_state_path}: duplicate study item {item_id}")
        seen.add(item_id)
        if item_id not in catalog_items:
            if item_id.startswith("S-K6-"):
                raise CatalogError(f"{study_state_path}: unknown steel catalog item {item_id}")
            continue
        if catalog_items[item_id].editorial_status != "source_checked":
            continue
        coarse = _coarse_status(raw)
        if coarse != "unstarted":
            projected[item_id] = coarse
    return dict(sorted(projected.items()))


def write_public_progress(output_path: Path) -> int:
    items = public_progress_from_local()
    document = {"version": 1, "items": items}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return len(items)
