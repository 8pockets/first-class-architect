"""Load and strictly validate the YAML source of truth."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Never, cast

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver

from principle_catalog.models import (
    Catalog,
    CatalogManifest,
    EditorialStatus,
    Principle,
    PrincipleType,
    PublicProgress,
    PublicProgressProjection,
    SourceAudit,
    SourceRef,
)


CATALOG_ROOT = Path("data/principles/steel")
MANIFEST_PATH = CATALOG_ROOT / "manifest.yaml"
PUBLIC_PROGRESS_PATH = Path("data/public_progress.yaml")
SOURCE_AUDIT_FILENAME = "source-audit.yaml"

_ID = re.compile(r"^S-K6-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
_SECTION_ID = re.compile(r"^K6-[0-9]{2}(?:-[0-9]{1,2})?$")
_QUESTION_CODE = re.compile(r"^(?:施工)?[0-9]{5}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TYPES: set[str] = {"principle", "rule", "identification"}
_EDITORIAL_STATUSES: set[str] = {"draft", "source_checked", "source_gap"}
_PUBLIC_PROGRESS: set[str] = {
    "unstarted",
    "learning",
    "reviewing",
    "retained_14d",
}
_GAP = "教材に記載なし"
_PAGE_KINDS = {
    "chapter_cover",
    "prior_question_table",
    "teaching_material",
    "worked_examples",
}


class CatalogError(ValueError):
    """Raised when canonical or projected catalog data violates its contract."""


class _StrictSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _StrictSafeLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictSafeLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _fail(path: Path, message: str) -> Never:
    raise CatalogError(f"{path}: {message}")


def _mapping(value: Any, path: Path, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(path, f"{label} must be a mapping with string keys")
    return cast(dict[str, Any], value)


def _list(value: Any, path: Path, label: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, f"{label} must be a list")
    return cast(list[Any], value)


def _str(value: Any, path: Path, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, f"{label} must be a non-empty string")
    return value.strip()


def _int(value: Any, path: Path, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, f"{label} must be an integer")
    return value


def _exact_keys(data: dict[str, Any], expected: set[str], path: Path, label: str) -> None:
    actual = set(data)
    if actual != expected:
        _fail(
            path,
            f"{label} keys must be {sorted(expected)}; got {sorted(actual)}",
        )


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.load(
            path.read_text(encoding="utf-8"),
            Loader=_StrictSafeLoader,
        )
    except FileNotFoundError as error:
        raise CatalogError(f"{path}: file not found") from error
    except yaml.YAMLError as error:
        raise CatalogError(f"{path}: invalid YAML") from error
    return _mapping(loaded, path, "document")


def _load_manifest(path: Path) -> CatalogManifest:
    data = _load_yaml(path)
    _exact_keys(data, {"version", "source", "audited_pages", "sections"}, path, "manifest")
    if _int(data["version"], path, "version") != 1:
        _fail(path, "version must be 1")

    source = _mapping(data["source"], path, "source")
    _exact_keys(source, {"title", "sha256", "scope_pages"}, path, "source")
    scope = _mapping(source["scope_pages"], path, "source.scope_pages")
    _exact_keys(scope, {"first", "last"}, path, "source.scope_pages")
    first = _int(scope["first"], path, "source.scope_pages.first")
    last = _int(scope["last"], path, "source.scope_pages.last")
    if first > last:
        _fail(path, "source page range is reversed")

    sha256 = _str(source["sha256"], path, "source.sha256")
    if not _SHA256.fullmatch(sha256):
        _fail(path, "source.sha256 must be a lowercase SHA-256 digest")

    audited = tuple(
        _int(page, path, "audited_pages entry")
        for page in _list(data["audited_pages"], path, "audited_pages")
    )
    expected_pages = tuple(range(first, last + 1))
    if audited != expected_pages:
        _fail(path, "audited_pages must cover the source range exactly and in order")

    raw_sections = _list(data["sections"], path, "sections")
    sections: list[Path] = []
    for raw in raw_sections:
        relative = Path(_str(raw, path, "sections entry"))
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".yaml":
            _fail(path, f"unsafe section path: {relative}")
        sections.append(path.parent / relative)
    if len(sections) != len(set(sections)):
        _fail(path, "sections contains duplicate paths")

    return CatalogManifest(
        source_title=_str(source["title"], path, "source.title"),
        source_sha256=sha256,
        first_page=first,
        last_page=last,
        audited_pages=audited,
        section_files=tuple(sections),
    )


def _load_source_audit(path: Path, manifest: CatalogManifest) -> SourceAudit:
    data = _load_yaml(path)
    _exact_keys(data, {"version", "table", "page_kinds"}, path, "source audit")
    if _int(data["version"], path, "version") != 1:
        _fail(path, "version must be 1")

    table = _mapping(data["table"], path, "table")
    _exact_keys(
        table,
        {"pages", "row_count", "primary_question_codes"},
        path,
        "table",
    )
    table_pages = tuple(
        _int(page, path, "table.pages entry")
        for page in _list(table["pages"], path, "table.pages")
    )
    if not table_pages or tuple(sorted(set(table_pages))) != table_pages:
        _fail(path, "table.pages must be non-empty, unique, and sorted")
    row_count = _int(table["row_count"], path, "table.row_count")
    primary_codes = _string_list(
        table["primary_question_codes"],
        path,
        "table.primary_question_codes",
    )
    if row_count != len(primary_codes):
        _fail(path, "table.row_count must match primary_question_codes")
    if any(not re.fullmatch(r"[0-9]{5}", code) for code in primary_codes):
        _fail(path, "primary question codes must be five digits")

    raw_page_kinds = _mapping(data["page_kinds"], path, "page_kinds")
    _exact_keys(raw_page_kinds, _PAGE_KINDS, path, "page_kinds")
    page_kinds: dict[str, tuple[int, ...]] = {}
    flattened: list[int] = []
    for kind in sorted(_PAGE_KINDS):
        pages = tuple(
            _int(page, path, f"page_kinds.{kind} entry")
            for page in _list(raw_page_kinds[kind], path, f"page_kinds.{kind}")
        )
        if tuple(sorted(set(pages))) != pages:
            _fail(path, f"page_kinds.{kind} must be unique and sorted")
        page_kinds[kind] = pages
        flattened.extend(pages)
    if tuple(sorted(flattened)) != manifest.audited_pages:
        _fail(path, "page_kinds must partition every audited page exactly once")
    if table_pages != page_kinds["prior_question_table"]:
        _fail(path, "table.pages must equal page_kinds.prior_question_table")

    return SourceAudit(
        table_pages=table_pages,
        table_row_count=row_count,
        primary_question_codes=primary_codes,
        page_kinds=page_kinds,
    )


def _string_list(value: Any, path: Path, label: str) -> tuple[str, ...]:
    values = tuple(_str(item, path, f"{label} entry") for item in _list(value, path, label))
    if len(values) != len(set(values)):
        _fail(path, f"{label} contains duplicates")
    return values


def _load_section(path: Path, manifest: CatalogManifest) -> tuple[Principle, ...]:
    data = _load_yaml(path)
    _exact_keys(data, {"version", "section", "principles"}, path, "section document")
    if _int(data["version"], path, "version") != 1:
        _fail(path, "version must be 1")

    section = _mapping(data["section"], path, "section")
    _exact_keys(section, {"id", "title", "order"}, path, "section")
    section_id = _str(section["id"], path, "section.id")
    if not _SECTION_ID.fullmatch(section_id):
        _fail(path, f"invalid section id: {section_id}")
    section_title = _str(section["title"], path, "section.title")
    section_order = _int(section["order"], path, "section.order")
    if section_order < 1:
        _fail(path, "section.order must be positive")

    principles: list[Principle] = []
    for index, raw in enumerate(_list(data["principles"], path, "principles"), start=1):
        item = _mapping(raw, path, f"principles[{index}]")
        _exact_keys(
            item,
            {
                "id",
                "order",
                "type",
                "principle",
                "conclusion",
                "reason",
                "conditions",
                "source",
                "prerequisites",
                "editorial_status",
            },
            path,
            f"principles[{index}]",
        )
        item_id = _str(item["id"], path, f"principles[{index}].id")
        if not _ID.fullmatch(item_id):
            _fail(path, f"invalid principle id: {item_id}")

        item_type = _str(item["type"], path, f"{item_id}.type")
        if item_type not in _TYPES:
            _fail(path, f"{item_id}.type must be one of {sorted(_TYPES)}")
        status = _str(item["editorial_status"], path, f"{item_id}.editorial_status")
        if status not in _EDITORIAL_STATUSES:
            _fail(path, f"{item_id}.editorial_status must be one of {sorted(_EDITORIAL_STATUSES)}")

        reason = _str(item["reason"], path, f"{item_id}.reason")
        conditions = _string_list(item["conditions"], path, f"{item_id}.conditions")
        if not conditions:
            _fail(path, f"{item_id}.conditions must not be empty")
        if status == "source_checked" and (
            reason == _GAP or _GAP in conditions
        ):
            _fail(path, f"{item_id} cannot be source_checked with a source gap")

        source = _mapping(item["source"], path, f"{item_id}.source")
        _exact_keys(source, {"pages", "question_codes"}, path, f"{item_id}.source")
        pages = tuple(
            _int(page, path, f"{item_id}.source.pages entry")
            for page in _list(source["pages"], path, f"{item_id}.source.pages")
        )
        if not pages or tuple(sorted(set(pages))) != pages:
            _fail(path, f"{item_id}.source.pages must be non-empty, unique, and sorted")
        if any(page < manifest.first_page or page > manifest.last_page for page in pages):
            _fail(path, f"{item_id}.source.pages falls outside the audited range")
        question_codes = _string_list(
            source["question_codes"], path, f"{item_id}.source.question_codes"
        )
        if any(not _QUESTION_CODE.fullmatch(code) for code in question_codes):
            _fail(path, f"{item_id} has an invalid question code")

        item_order = _int(item["order"], path, f"{item_id}.order")
        if item_order < 1:
            _fail(path, f"{item_id}.order must be positive")
        principles.append(
            Principle(
                id=item_id,
                section_id=section_id,
                section_title=section_title,
                section_order=section_order,
                order=item_order,
                type=cast(PrincipleType, item_type),
                principle=_str(item["principle"], path, f"{item_id}.principle"),
                conclusion=_str(item["conclusion"], path, f"{item_id}.conclusion"),
                reason=reason,
                conditions=conditions,
                source=SourceRef(pages=pages, question_codes=question_codes),
                prerequisites=_string_list(
                    item["prerequisites"], path, f"{item_id}.prerequisites"
                ),
                editorial_status=cast(EditorialStatus, status),
            )
        )
    return tuple(principles)


def load_catalog(manifest_path: Path = MANIFEST_PATH) -> Catalog:
    manifest = _load_manifest(manifest_path)
    audit = _load_source_audit(manifest_path.parent / SOURCE_AUDIT_FILENAME, manifest)
    principles = tuple(
        principle
        for section_path in manifest.section_files
        for principle in _load_section(section_path, manifest)
    )
    if not principles:
        _fail(manifest_path, "catalog must contain at least one principle")

    ids = [item.id for item in principles]
    if len(ids) != len(set(ids)):
        duplicates = sorted(item_id for item_id in set(ids) if ids.count(item_id) > 1)
        _fail(manifest_path, f"duplicate principle IDs: {duplicates}")
    known = set(ids)
    normalized_names: dict[str, str] = {}
    for item in principles:
        normalized_name = unicodedata.normalize("NFKC", item.principle).strip()
        prior_name_id = normalized_names.setdefault(normalized_name, item.id)
        if prior_name_id != item.id:
            _fail(
                manifest_path,
                f"duplicate principle title for {prior_name_id} and {item.id}",
            )
        missing = sorted(set(item.prerequisites) - known)
        if missing:
            _fail(manifest_path, f"{item.id} has unknown prerequisites: {missing}")
        if item.id in item.prerequisites:
            _fail(manifest_path, f"{item.id} cannot depend on itself")

    visited: set[str] = set()
    visiting: set[str] = set()
    by_id = {item.id: item for item in principles}
    for item in principles:
        if item.editorial_status != "source_checked":
            continue
        unavailable = sorted(
            prerequisite
            for prerequisite in item.prerequisites
            if by_id[prerequisite].editorial_status != "source_checked"
        )
        if unavailable:
            _fail(
                manifest_path,
                f"{item.id} has unpublished prerequisites: {unavailable}",
            )

    def visit(item_id: str) -> None:
        if item_id in visited:
            return
        if item_id in visiting:
            _fail(manifest_path, f"prerequisite cycle includes {item_id}")
        visiting.add(item_id)
        for prerequisite in by_id[item_id].prerequisites:
            visit(prerequisite)
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in ids:
        visit(item_id)

    section_orders: dict[str, int] = {}
    section_ids_by_order: dict[int, str] = {}
    section_titles: dict[str, str] = {}
    item_orders: set[tuple[str, int]] = set()
    for item in principles:
        prior = section_orders.setdefault(item.section_id, item.section_order)
        if prior != item.section_order:
            _fail(manifest_path, f"section {item.section_id} has conflicting order values")
        prior_id = section_ids_by_order.setdefault(item.section_order, item.section_id)
        if prior_id != item.section_id:
            _fail(
                manifest_path,
                f"section order {item.section_order} is shared by {prior_id} and {item.section_id}",
            )
        prior_title = section_titles.setdefault(item.section_id, item.section_title)
        if prior_title != item.section_title:
            _fail(manifest_path, f"section {item.section_id} has conflicting titles")
        order_key = (item.section_id, item.order)
        if order_key in item_orders:
            _fail(manifest_path, f"section {item.section_id} has duplicate item order {item.order}")
        item_orders.add(order_key)

    covered_pages = {page for item in principles for page in item.source.pages}
    required_content_pages = set(manifest.audited_pages) - set(
        audit.page_kinds["chapter_cover"]
    )
    missing_pages = sorted(required_content_pages - covered_pages)
    if missing_pages:
        _fail(manifest_path, f"content pages without catalog coverage: {missing_pages}")
    catalog_codes = {code for item in principles for code in item.source.question_codes}
    missing_codes = sorted(set(audit.primary_question_codes) - catalog_codes)
    if missing_codes:
        _fail(manifest_path, f"audited table codes without catalog coverage: {missing_codes}")

    sorted_principles = tuple(
        sorted(principles, key=lambda item: (item.section_order, item.order, item.id))
    )
    return Catalog(manifest=manifest, audit=audit, principles=sorted_principles)


def load_public_progress(path: Path = PUBLIC_PROGRESS_PATH) -> PublicProgressProjection:
    data = _load_yaml(path)
    _exact_keys(data, {"version", "items"}, path, "public progress")
    if _int(data["version"], path, "version") != 1:
        _fail(path, "version must be 1")
    raw_items = _mapping(data["items"], path, "items")
    items: dict[str, PublicProgress] = {}
    for item_id, raw_status in raw_items.items():
        if not _ID.fullmatch(item_id):
            _fail(path, f"invalid principle id: {item_id}")
        status = _str(raw_status, path, f"items.{item_id}")
        if status not in _PUBLIC_PROGRESS:
            _fail(path, f"items.{item_id} must be one of {sorted(_PUBLIC_PROGRESS)}")
        items[item_id] = cast(PublicProgress, status)
    return PublicProgressProjection(items=items)


def validate_public_progress(
    catalog: Catalog,
    projection: PublicProgressProjection,
) -> None:
    known = {item.id for item in catalog.principles}
    unknown = sorted(set(projection.items) - known)
    if unknown:
        raise CatalogError(f"public progress references unknown IDs: {unknown}")
    published = {
        item.id for item in catalog.principles if item.editorial_status == "source_checked"
    }
    unpublished = sorted(set(projection.items) - published)
    if unpublished:
        raise CatalogError(f"public progress references unpublished IDs: {unpublished}")
