"""Bridge the canonical catalog to the private local study state."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from principle_catalog.catalog import (
    CatalogError,
    coverage_assignment,
    coverage_introduction_order,
    display_facets,
    display_principles,
    load_catalog,
    resolve_principle,
)
from principle_catalog.models import Catalog, Principle, PublicProgress
from principle_catalog.study_status import coarse_study_status


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


def _learning_order(catalog: Catalog) -> tuple[Principle, ...]:
    """Return the canonical published display order for new private records."""

    return display_principles(catalog, published_only=True)


def _coverage_study_statuses(
    catalog: Catalog,
    state: dict[str, Any],
) -> dict[str, PublicProgress]:
    raw_items = state.get("items")
    if not isinstance(raw_items, list):
        raise CatalogError("study state items must be a list")
    covered = {
        item.id for item in coverage_introduction_order(catalog, ceiling=3)
    }
    statuses: dict[str, PublicProgress] = {}
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            raise CatalogError(f"study state items[{index}] must have a string id")
        item_id = raw["id"]
        if item_id not in covered:
            continue
        if item_id in statuses:
            raise CatalogError(f"study state has duplicate coverage item {item_id}")
        statuses[item_id] = coarse_study_status(raw)
    return statuses


def unlocked_coverage_tier(catalog: Catalog, state: dict[str, Any]) -> int:
    """Return the fixed tier unlocked by initial-introduction completion only."""

    statuses = _coverage_study_statuses(catalog, state)
    for tier in (1, 2):
        tier_items = coverage_introduction_order(catalog, ceiling=tier)
        if any(
            coverage_assignment(catalog, item).tier == tier
            and statuses.get(item.id, "unstarted") == "unstarted"
            for item in tier_items
        ):
            return tier
    return 3


def new_study_candidates(
    catalog: Catalog,
    state: dict[str, Any],
    *,
    ceiling: int | None = None,
) -> tuple[Principle, ...]:
    """List eligible new items without interpreting the urgent/review queue."""

    statuses = _coverage_study_statuses(catalog, state)
    selected_ceiling = (
        unlocked_coverage_tier(catalog, state) if ceiling is None else ceiling
    )
    return tuple(
        item
        for item in coverage_introduction_order(catalog, selected_ceiling)
        if statuses.get(item.id, "unstarted") == "unstarted"
    )


def new_study_candidates_from_path(
    path: Path = LOCAL_STUDY_STATE,
    *,
    ceiling: int | None = None,
) -> tuple[Principle, ...]:
    """Load local state and list eligible new items without writing it."""

    catalog = load_catalog()
    return new_study_candidates(catalog, _load_state(path), ceiling=ceiling)


def sync_study_items(path: Path = LOCAL_STUDY_STATE) -> tuple[str, ...]:
    """Append source-checked catalog IDs without changing existing study records."""

    state = _load_state(path)
    catalog = load_catalog()
    known_catalog_ids = {item.id for item in catalog.principles}
    retired_catalog_ids = set(catalog.migration.retired)
    existing_ids: list[str] = []
    for index, raw in enumerate(state["items"], start=1):
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            raise CatalogError(f"{path}: items[{index}] must have a string id")
        existing_ids.append(raw["id"])
    if len(existing_ids) != len(set(existing_ids)):
        raise CatalogError(f"{path}: duplicate study item IDs")
    unknown_steel = sorted(
        item_id
        for item_id in set(existing_ids) - known_catalog_ids - retired_catalog_ids
        if item_id.startswith("S-K6-")
    )
    if unknown_steel:
        raise CatalogError(f"{path}: unknown steel catalog items: {unknown_steel}")

    added: list[str] = []
    seen = set(existing_ids)
    for item in _learning_order(catalog):
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


def study_brief(item_id: str, *, reveal: bool = False) -> str:
    """Render one catalog question with its always-visible answer and explanation.

    ``reveal`` remains a no-op for CLI compatibility with the former hidden-answer
    contract.
    """

    catalog = load_catalog()
    item = resolve_principle(catalog, item_id).require_one()
    if item.editorial_status != "source_checked" or item.question is None:
        raise CatalogError(f"catalog item is not source-checked: {item_id}")
    facets = display_facets(catalog, item)
    question = (
        f"# {item.principle}\n\n"
        f"公開コード: `{item.code}`\n\n"
        f"内部キー: `{item.id}`\n\n"
        f"## 確認問題（自作・2択）\n\n{item.question.prompt}\n\n"
        f"A. {item.question.choice_a}\n\n"
        f"B. {item.question.choice_b}\n"
    )
    blocks: list[str] = []
    for facet in (facets.primary, facets.secondary, facets.tertiary):
        if not facet.values:
            body = "—"
        elif len(facet.values) == 1:
            body = facet.values[0]
        else:
            body = "\n".join(f"- {value}" for value in facet.values)
        blocks.append(f"## {facet.label}\n\n{body}")
    rendered_blocks = "\n\n".join(blocks)
    return (
        f"{question}\n"
        f"正解: **{item.question.correct}**\n\n"
        f"{rendered_blocks}\n"
    )
