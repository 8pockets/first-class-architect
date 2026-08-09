"""Bridge the canonical catalog to the private local study state."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from principle_catalog.catalog import CatalogError, load_catalog
from principle_catalog.models import Principle


LOCAL_STUDY_STATE = Path(".study/state.json")


def _load_state(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CatalogError(f"{path}: local study state not found") from error
    except json.JSONDecodeError as error:
        raise CatalogError(f"{path}: invalid JSON") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise CatalogError(f"{path}: items must be a list")
    return raw


def _catalog_item(item: Principle) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.principle,
        "page": item.source.pages[0],
        "status": "not_started",
        "retention_anchor": False,
        "stage": "day0",
        "last_passed_on": None,
        "next_due_on": None,
        "consecutive_failures": 0,
    }


def _learning_order(items: tuple[Principle, ...]) -> tuple[Principle, ...]:
    """Return prerequisite-first order with canonical PDF order as the tie-breaker."""

    eligible = tuple(item for item in items if item.editorial_status == "source_checked")
    by_id = {item.id: item for item in eligible}
    position = {item.id: index for index, item in enumerate(eligible)}
    remaining = {
        item.id: {dependency for dependency in item.prerequisites if dependency in by_id}
        for item in eligible
    }
    ordered: list[Principle] = []
    while remaining:
        ready = sorted(
            (item_id for item_id, dependencies in remaining.items() if not dependencies),
            key=position.__getitem__,
        )
        if not ready:
            raise CatalogError("catalog prerequisites do not form a learning sequence")
        for item_id in ready:
            ordered.append(by_id[item_id])
            del remaining[item_id]
        ready_set = set(ready)
        for dependencies in remaining.values():
            dependencies.difference_update(ready_set)
    return tuple(ordered)


def sync_study_items(path: Path = LOCAL_STUDY_STATE) -> tuple[str, ...]:
    """Append source-checked catalog IDs without changing existing study records."""

    state = _load_state(path)
    catalog = load_catalog()
    known_catalog_ids = {item.id for item in catalog.principles}
    existing_ids: list[str] = []
    for index, raw in enumerate(state["items"], start=1):
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            raise CatalogError(f"{path}: items[{index}] must have a string id")
        existing_ids.append(raw["id"])
    if len(existing_ids) != len(set(existing_ids)):
        raise CatalogError(f"{path}: duplicate study item IDs")
    unknown_steel = sorted(
        item_id
        for item_id in set(existing_ids) - known_catalog_ids
        if item_id.startswith("S-K6-")
    )
    if unknown_steel:
        raise CatalogError(f"{path}: unknown steel catalog items: {unknown_steel}")

    added: list[str] = []
    seen = set(existing_ids)
    for item in _learning_order(catalog.principles):
        if item.id in seen:
            continue
        state["items"].append(_catalog_item(item))
        seen.add(item.id)
        added.append(item.id)

    if not added:
        return ()

    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return tuple(added)


def study_brief(item_id: str) -> str:
    """Render the four always-visible learning fields for one catalog item."""

    catalog = load_catalog()
    item = next((candidate for candidate in catalog.principles if candidate.id == item_id), None)
    if item is None:
        raise CatalogError(f"unknown catalog item: {item_id}")
    conditions = "\n".join(f"- {condition}" for condition in item.conditions)
    return (
        f"# {item.principle}\n\n"
        f"項目ID: `{item.id}`\n\n"
        f"## 原理\n\n{item.principle}\n\n"
        f"## 結論\n\n{item.conclusion}\n\n"
        f"## 理由\n\n{item.reason}\n\n"
        f"## 結論を左右する条件\n\n{conditions}\n"
    )
