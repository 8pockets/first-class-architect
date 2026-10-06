"""Load and strictly validate the YAML source of truth."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import replace
from pathlib import Path
from typing import Any, Never, cast
from urllib.parse import urlparse

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver

from principle_catalog.models import (
    AuthoritativeSource,
    AuthoritativeSourceKind,
    AuthoritativeSourceSchema,
    BinaryQuestion,
    Catalog,
    CatalogManifest,
    CardDisplayFacets,
    ChoiceLabel,
    CompletenessStatus,
    ContentReviewSchema,
    ContentVerification,
    CoverageAssignment,
    CoverageConstraints,
    CoverageReason,
    CoverageRegistry,
    CoverageScheme,
    CoverageSchemeStatus,
    CoverageTier,
    CoverageTierDefinition,
    DisplaySchema,
    DisplayFacet,
    EditorialStatus,
    IdentityRegistry,
    IdentificationDisplayContent,
    MigrationOperation,
    MigrationRecord,
    MigrationRegistry,
    Principle,
    PrincipleIdentity,
    PrincipleType,
    PublicProgress,
    PublicProgressProjection,
    QuestionEdition,
    QuestionEditionRegistry,
    QuestionEditionStatus,
    RuleDisplayContent,
    SourceSupport,
    SourceAudit,
    SourceRef,
    StatementSourceStatus,
    TaxonomyGroup,
    TaxonomyProjection,
    TaxonomySubtopic,
    TypeDisplayLabels,
)


CATALOG_ROOT = Path("data/principles/steel")
MANIFEST_PATH = CATALOG_ROOT / "manifest.yaml"
PUBLIC_PROGRESS_PATH = Path("data/public_progress.yaml")
SOURCE_AUDIT_FILENAME = "source-audit.yaml"
QUESTION_EDITIONS_PATH = CATALOG_ROOT / "question-editions.yaml"
IDENTITIES_PATH = CATALOG_ROOT / "identities.yaml"
MIGRATION_PATH = CATALOG_ROOT / "migration.yaml"
COVERAGE_TIERS_PATH = CATALOG_ROOT / "coverage-tiers.yaml"

_ID = re.compile(r"^S-K6-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
_SECTION_ID = re.compile(r"^K6-[0-9]{2}(?:-[0-9]{1,2})?$")
_QUESTION_CODE = re.compile(r"^(?:施工)?[0-9]{5}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PUBLIC_CODE = re.compile(
    r"^structure\.steel\.[a-z0-9]+(?:[.-][a-z0-9]+)*$"
)
_TAXONOMY_ID = re.compile(r"^steel\.[a-z0-9]+(?:[.-][a-z0-9]+)*$")
_EDITION_ID = re.compile(r"^K6-R[1-9][0-9]*$")
_COVERAGE_SCHEME_ID = re.compile(r"^steel-coverage-v[1-9][0-9]*$")
_TYPES: set[str] = {"principle", "rule", "identification"}
_EDITORIAL_STATUSES: set[str] = {"draft", "source_checked", "source_gap"}
_PUBLIC_PROGRESS: set[str] = {
    "unstarted",
    "learning",
    "reviewing",
    "retained_14d",
}
_GAP = "教材に記載なし"
_CHOICE_LABELS: set[str] = {"A", "B"}
_QUESTION_PROMPT_SUFFIX = "正しい結論はどちらか。"
_QUESTION_FORBIDDEN = {
    "説明しなさい",
    "述べなさい",
    "誤っている",
    "正しくない",
}
_ANSWER_CUE_FORBIDDEN = {
    "正解",
    "不正解",
    "誤答",
    "答え",
}
_ANSWER_SYMBOL_CUES = {"(○)", "(×)", "[○]", "[×]", "【○】", "【×】"}
_CHOICE_FORBIDDEN = {
    "必ず",
    "絶対",
    "両方",
    "双方",
    "いずれも",
    "どちらも",
    "どちらでもない",
}
_PAGE_KINDS = {
    "chapter_cover",
    "prior_question_table",
    "teaching_material",
    "worked_examples",
}
_PROJECTION_FILENAMES = {
    "taxonomy": "taxonomy.yaml",
    "identities": "identities.yaml",
    "migration": "migration.yaml",
    "question_editions": "question-editions.yaml",
    "coverage_tiers": "coverage-tiers.yaml",
}
_PROJECTION_NAMES = set(_PROJECTION_FILENAMES)
_AUTHORITATIVE_SOURCE_KINDS: set[str] = {
    "law",
    "notification",
    "jis",
    "aij",
    "government_spec",
    "government_research",
    "professional_body",
    "local_government",
    "official_exam",
    "study_material",
}
_SOURCE_SUPPORTS: set[str] = {"statement", "explanation", "conditions"}
_STATEMENT_SOURCE_STATUSES: set[str] = {"verified", "gap", "unreviewed"}
_COMPLETENESS_STATUSES: set[str] = {
    "complete",
    "partial",
    "missing",
    "unreviewed",
}
_QUESTION_EDITION_STATUSES: set[str] = {"archived", "current"}
_COVERAGE_SCHEME_STATUSES: set[str] = {"archived", "current"}
_COVERAGE_REASONS: set[str] = {
    "coverage_representative",
    "prerequisite",
    "standard_application",
    "basic_identification",
    "exception_detail",
    "integrated_judgment",
}
_COVERAGE_TIERS: tuple[int, ...] = (1, 2, 3)
_COVERAGE_TIER_DEFINITIONS = {
    1: ("foundation", "骨格"),
    2: ("standard", "標準"),
    3: ("advanced", "発展"),
}
_MIGRATION_OPERATIONS: set[str] = {"split", "merge", "rename"}
_PROGRESS_POLICIES: set[str] = {
    "reset_targets_to_unstarted",
    "preserve_active_target_only",
}


class CatalogError(ValueError):
    """Raised when canonical or projected catalog data violates its contract."""


class AmbiguousPrincipleIdentifier(CatalogError):
    """Raised when an identifier has a split lineage and cannot name one card."""


class UnknownPrincipleIdentifier(CatalogError):
    """Raised when no active or legacy identity matches an identifier."""


class PrincipleResolution:
    """An explicit one-or-many result from the central identity resolver."""

    def __init__(
        self,
        identifier: str,
        principles: tuple[Principle, ...],
        migration: MigrationRecord | None = None,
        historically_split: bool = False,
    ) -> None:
        self.identifier = identifier
        self.principles = principles
        self.migration = migration
        self.historically_split = historically_split

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.principles)

    @property
    def is_split(self) -> bool:
        return self.historically_split or len(self.principles) > 1

    def require_one(self) -> Principle:
        if self.is_split or len(self.principles) != 1:
            targets = ", ".join(self.keys)
            raise AmbiguousPrincipleIdentifier(
                f"split identifier {self.identifier!r} resolves to: {targets}"
            )
        return self.principles[0]


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


def _coverage_tier_mapping(
    value: Any,
    path: Path,
    label: str,
) -> dict[int, Any]:
    if not isinstance(value, dict) or any(
        isinstance(key, bool) or not isinstance(key, int) for key in value
    ):
        _fail(path, f"{label} must be a mapping with integer tier keys")
    tiers = cast(dict[int, Any], value)
    if set(tiers) != set(_COVERAGE_TIERS):
        _fail(path, f"{label} must define tiers {list(_COVERAGE_TIERS)}")
    return tiers


def _contains_invisible(value: str) -> bool:
    return any(unicodedata.category(character) in {"Cc", "Cf"} for character in value)


def _normalized_choice(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", normalized)


def _has_repeating_answer_period(answers: tuple[str, ...]) -> bool:
    for period in range(1, len(answers) // 2 + 1):
        if len(answers) % period != 0:
            continue
        if all(answer == answers[index % period] for index, answer in enumerate(answers)):
            return True
    return False


def _print_registry_sha256(print_numbers: dict[str, int]) -> str:
    assignments = [
        {"id": item_id, "number": number}
        for item_id, number in sorted(
            print_numbers.items(),
            key=lambda assignment: assignment[1],
        )
    ]
    canonical = json.dumps(
        assignments,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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


def _parse_print_registry(
    registry: Any,
    path: Path,
) -> tuple[int, dict[str, int], str]:
    print_registry = _mapping(registry, path, "print_registry")
    _exact_keys(
        print_registry,
        {"next_number", "assignments", "content_sha256"},
        path,
        "print_registry",
    )
    next_print_number = _int(
        print_registry["next_number"],
        path,
        "print_registry.next_number",
    )
    if next_print_number < 1:
        _fail(path, "print_registry.next_number must be positive")
    raw_print_numbers = _mapping(
        print_registry["assignments"],
        path,
        "print_registry.assignments",
    )
    print_numbers: dict[str, int] = {}
    for item_id, raw_number in raw_print_numbers.items():
        if not _ID.fullmatch(item_id):
            _fail(path, f"print_registry has invalid principle id: {item_id}")
        number = _int(
            raw_number,
            path,
            f"print_registry.assignments.{item_id}",
        )
        if number < 1:
            _fail(path, "print registry numbers must be positive")
        print_numbers[item_id] = number
    numbers = sorted(print_numbers.values())
    if len(numbers) != len(set(numbers)):
        _fail(path, "print registry numbers must be unique")
    if numbers != list(range(1, next_print_number)):
        _fail(path, "print registry must be contiguous up to next_number")
    print_registry_sha256 = _str(
        print_registry["content_sha256"],
        path,
        "print_registry.content_sha256",
    )
    if not _SHA256.fullmatch(print_registry_sha256):
        _fail(
            path,
            "print_registry.content_sha256 must be a lowercase SHA-256 digest",
        )
    if _print_registry_sha256(print_numbers) != print_registry_sha256:
        _fail(path, "print numbers differ from the permanent print registry snapshot")
    return next_print_number, print_numbers, print_registry_sha256


def _load_manifest(path: Path) -> CatalogManifest:
    data = _load_yaml(path)
    _exact_keys(
        data,
        {
            "version",
            "source",
            "audited_pages",
            "sections",
            "inventory",
            "question_audit",
            "print_registry",
            "projections",
            "authoritative_source_schema",
            "content_review_schema",
        },
        path,
        "manifest",
    )
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

    inventory = _mapping(data["inventory"], path, "inventory")
    _exact_keys(inventory, {"total", "editorial_status"}, path, "inventory")
    expected_total = _int(inventory["total"], path, "inventory.total")
    if expected_total < 1:
        _fail(path, "inventory.total must be positive")
    raw_status_counts = _mapping(
        inventory["editorial_status"],
        path,
        "inventory.editorial_status",
    )
    _exact_keys(
        raw_status_counts,
        _EDITORIAL_STATUSES,
        path,
        "inventory.editorial_status",
    )
    expected_status_counts = {
        cast(EditorialStatus, status): _int(
            raw_status_counts[status],
            path,
            f"inventory.editorial_status.{status}",
        )
        for status in sorted(_EDITORIAL_STATUSES)
    }
    if any(count < 0 for count in expected_status_counts.values()):
        _fail(path, "inventory.editorial_status counts must not be negative")
    if sum(expected_status_counts.values()) != expected_total:
        _fail(path, "inventory editorial status counts must equal total")

    question_audit = _mapping(data["question_audit"], path, "question_audit")
    _exact_keys(
        question_audit,
        {
            "answer_positions",
            "content_sha256",
            "order_sha256",
            "taxonomy_sha256",
            "prerequisites_sha256",
            "identities_sha256",
            "migration_sha256",
            "coverage_tiers_sha256",
        },
        path,
        "question_audit",
    )
    raw_answer_counts = _mapping(
        question_audit["answer_positions"],
        path,
        "question_audit.answer_positions",
    )
    _exact_keys(
        raw_answer_counts,
        _CHOICE_LABELS,
        path,
        "question_audit.answer_positions",
    )
    expected_answer_counts = {
        cast(ChoiceLabel, label): _int(
            raw_answer_counts[label],
            path,
            f"question_audit.answer_positions.{label}",
        )
        for label in sorted(_CHOICE_LABELS)
    }
    if any(count < 0 for count in expected_answer_counts.values()):
        _fail(path, "question_audit answer counts must not be negative")
    audit_hashes: dict[str, str] = {}
    for name in (
        "content_sha256",
        "order_sha256",
        "taxonomy_sha256",
        "prerequisites_sha256",
        "identities_sha256",
        "migration_sha256",
        "coverage_tiers_sha256",
    ):
        digest = _str(question_audit[name], path, f"question_audit.{name}")
        if not _SHA256.fullmatch(digest):
            _fail(
                path,
                f"question_audit.{name} must be a lowercase SHA-256 digest",
            )
        audit_hashes[name] = digest

    raw_projections = _mapping(data["projections"], path, "projections")
    _exact_keys(raw_projections, _PROJECTION_NAMES, path, "projections")
    projection_paths: dict[str, Path] = {}
    for name in sorted(_PROJECTION_NAMES):
        raw_relative = _str(raw_projections[name], path, f"projections.{name}")
        expected_filename = _PROJECTION_FILENAMES[name]
        if raw_relative != expected_filename:
            _fail(
                path,
                f"projections.{name} must be {expected_filename}",
            )
        relative = Path(raw_relative)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".yaml":
            _fail(path, f"unsafe projection path: {relative}")
        projection_paths[name] = path.parent / relative
    if len(set(projection_paths.values())) != len(projection_paths):
        _fail(path, "projection paths must be unique")

    raw_authoritative_schema = _mapping(
        data["authoritative_source_schema"],
        path,
        "authoritative_source_schema",
    )
    _exact_keys(
        raw_authoritative_schema,
        {
            "allowed_kinds",
            "required_fields",
            "optional_fields",
            "allowed_supports",
        },
        path,
        "authoritative_source_schema",
    )
    allowed_kinds = _string_list(
        raw_authoritative_schema["allowed_kinds"],
        path,
        "authoritative_source_schema.allowed_kinds",
    )
    required_source_fields = _string_list(
        raw_authoritative_schema["required_fields"],
        path,
        "authoritative_source_schema.required_fields",
    )
    optional_source_fields = _string_list(
        raw_authoritative_schema["optional_fields"],
        path,
        "authoritative_source_schema.optional_fields",
    )
    allowed_supports = _string_list(
        raw_authoritative_schema["allowed_supports"],
        path,
        "authoritative_source_schema.allowed_supports",
    )
    if set(allowed_kinds) != _AUTHORITATIVE_SOURCE_KINDS:
        _fail(path, "authoritative_source_schema.allowed_kinds is not supported")
    if set(required_source_fields) != {"kind", "title", "locator", "supports"}:
        _fail(path, "authoritative_source_schema.required_fields is not supported")
    if set(optional_source_fields) != {"url"}:
        _fail(path, "authoritative_source_schema.optional_fields is not supported")
    if set(allowed_supports) != _SOURCE_SUPPORTS:
        _fail(path, "authoritative_source_schema.allowed_supports is not supported")
    authoritative_source_schema = AuthoritativeSourceSchema(
        allowed_kinds=cast(tuple[AuthoritativeSourceKind, ...], allowed_kinds),
        required_fields=required_source_fields,
        optional_fields=optional_source_fields,
        allowed_supports=cast(tuple[SourceSupport, ...], allowed_supports),
    )

    raw_review_schema = _mapping(
        data["content_review_schema"], path, "content_review_schema"
    )
    _exact_keys(
        raw_review_schema,
        {
            "statement_source",
            "explanation_completeness",
            "conditions_completeness",
        },
        path,
        "content_review_schema",
    )
    statement_source_values = _string_list(
        raw_review_schema["statement_source"],
        path,
        "content_review_schema.statement_source",
    )
    explanation_values = _string_list(
        raw_review_schema["explanation_completeness"],
        path,
        "content_review_schema.explanation_completeness",
    )
    conditions_values = _string_list(
        raw_review_schema["conditions_completeness"],
        path,
        "content_review_schema.conditions_completeness",
    )
    if set(statement_source_values) != _STATEMENT_SOURCE_STATUSES:
        _fail(path, "content_review_schema.statement_source is not supported")
    if set(explanation_values) != _COMPLETENESS_STATUSES:
        _fail(path, "content_review_schema.explanation_completeness is not supported")
    if set(conditions_values) != _COMPLETENESS_STATUSES:
        _fail(path, "content_review_schema.conditions_completeness is not supported")
    content_review_schema = ContentReviewSchema(
        statement_source=cast(
            tuple[StatementSourceStatus, ...], statement_source_values
        ),
        explanation_completeness=cast(
            tuple[CompletenessStatus, ...], explanation_values
        ),
        conditions_completeness=cast(
            tuple[CompletenessStatus, ...], conditions_values
        ),
    )

    next_print_number, print_numbers, print_registry_sha256 = _parse_print_registry(
        data["print_registry"],
        path,
    )

    return CatalogManifest(
        source_title=_str(source["title"], path, "source.title"),
        source_sha256=sha256,
        first_page=first,
        last_page=last,
        audited_pages=audited,
        section_files=tuple(sections),
        expected_total=expected_total,
        expected_status_counts=expected_status_counts,
        expected_answer_counts=expected_answer_counts,
        question_audit_sha256=audit_hashes["content_sha256"],
        question_order_sha256=audit_hashes["order_sha256"],
        taxonomy_audit_sha256=audit_hashes["taxonomy_sha256"],
        prerequisites_audit_sha256=audit_hashes["prerequisites_sha256"],
        identities_audit_sha256=audit_hashes["identities_sha256"],
        migration_audit_sha256=audit_hashes["migration_sha256"],
        coverage_tiers_audit_sha256=audit_hashes["coverage_tiers_sha256"],
        next_print_number=next_print_number,
        print_numbers=print_numbers,
        print_registry_sha256=print_registry_sha256,
        projection_paths=projection_paths,
        authoritative_source_schema=authoritative_source_schema,
        content_review_schema=content_review_schema,
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


def _load_authoritative_sources(
    value: Any,
    path: Path,
    label: str,
) -> tuple[AuthoritativeSource, ...]:
    sources: list[AuthoritativeSource] = []
    for index, raw in enumerate(_list(value, path, label), start=1):
        source_label = f"{label}[{index}]"
        source = _mapping(raw, path, source_label)
        expected = {"kind", "title", "locator", "supports"}
        if "url" in source:
            expected.add("url")
        _exact_keys(source, expected, path, source_label)
        kind = _str(source["kind"], path, f"{source_label}.kind")
        if kind not in _AUTHORITATIVE_SOURCE_KINDS:
            _fail(
                path,
                f"{source_label}.kind must be one of "
                f"{sorted(_AUTHORITATIVE_SOURCE_KINDS)}",
            )
        supports = _string_list(
            source["supports"], path, f"{source_label}.supports"
        )
        if not supports or not set(supports) <= _SOURCE_SUPPORTS:
            _fail(
                path,
                f"{source_label}.supports must use "
                f"{sorted(_SOURCE_SUPPORTS)}",
            )
        url: str | None = None
        if "url" in source:
            url = _str(source["url"], path, f"{source_label}.url")
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc:
                _fail(path, f"{source_label}.url must be an absolute HTTPS URL")
        sources.append(
            AuthoritativeSource(
                kind=cast(AuthoritativeSourceKind, kind),
                title=_str(source["title"], path, f"{source_label}.title"),
                locator=_str(source["locator"], path, f"{source_label}.locator"),
                url=url,
                supports=cast(tuple[SourceSupport, ...], supports),
            )
        )
    identities = [(source.kind, source.title, source.locator) for source in sources]
    if len(identities) != len(set(identities)):
        _fail(path, f"{label} contains duplicate sources")
    return tuple(sources)


def _default_verification(status: str) -> ContentVerification:
    if status == "source_checked":
        return ContentVerification("verified", "complete", "complete")
    if status == "source_gap":
        return ContentVerification("verified", "missing", "complete")
    return ContentVerification("unreviewed", "unreviewed", "unreviewed")


def _load_verification(
    value: Any,
    path: Path,
    label: str,
) -> ContentVerification:
    verification = _mapping(value, path, label)
    _exact_keys(
        verification,
        {
            "statement_source",
            "explanation_completeness",
            "conditions_completeness",
        },
        path,
        label,
    )
    statement = _str(
        verification["statement_source"], path, f"{label}.statement_source"
    )
    explanation = _str(
        verification["explanation_completeness"],
        path,
        f"{label}.explanation_completeness",
    )
    conditions = _str(
        verification["conditions_completeness"],
        path,
        f"{label}.conditions_completeness",
    )
    if statement not in _STATEMENT_SOURCE_STATUSES:
        _fail(path, f"{label}.statement_source has an unsupported value")
    if explanation not in _COMPLETENESS_STATUSES:
        _fail(path, f"{label}.explanation_completeness has an unsupported value")
    if conditions not in _COMPLETENESS_STATUSES:
        _fail(path, f"{label}.conditions_completeness has an unsupported value")
    return ContentVerification(
        statement_source=cast(StatementSourceStatus, statement),
        explanation_completeness=cast(CompletenessStatus, explanation),
        conditions_completeness=cast(CompletenessStatus, conditions),
    )


def _load_display_content(
    value: Any,
    item_type: str,
    path: Path,
    label: str,
) -> RuleDisplayContent | IdentificationDisplayContent:
    content = _mapping(value, path, label)
    if item_type == "rule":
        _exact_keys(
            content,
            {"rule", "applicability", "numbers_exceptions"},
            path,
            label,
        )
        applicability = _string_list(
            content["applicability"], path, f"{label}.applicability"
        )
        if not applicability:
            _fail(path, f"{label}.applicability must not be empty")
        return RuleDisplayContent(
            rule=_str(content["rule"], path, f"{label}.rule"),
            applicability=applicability,
            numbers_exceptions=_string_list(
                content["numbers_exceptions"],
                path,
                f"{label}.numbers_exceptions",
            ),
        )
    if item_type == "identification":
        _exact_keys(
            content,
            {"definition", "distinguishing_conditions", "confusable_points"},
            path,
            label,
        )
        distinguishing = _string_list(
            content["distinguishing_conditions"],
            path,
            f"{label}.distinguishing_conditions",
        )
        if not distinguishing:
            _fail(path, f"{label}.distinguishing_conditions must not be empty")
        return IdentificationDisplayContent(
            definition=_str(content["definition"], path, f"{label}.definition"),
            distinguishing_conditions=distinguishing,
            confusable_points=_string_list(
                content["confusable_points"],
                path,
                f"{label}.confusable_points",
            ),
        )
    _fail(path, f"{label} is only allowed for rule or identification entries")


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
        item_keys = {
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
        }
        if "question" in item:
            item_keys.add("question")
        if "related" in item:
            item_keys.add("related")
        if "verification" in item:
            item_keys.add("verification")
        if "display_content" in item:
            item_keys.add("display_content")
        _exact_keys(
            item,
            item_keys,
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

        question: BinaryQuestion | None = None
        if "question" in item:
            question_data = _mapping(item["question"], path, f"{item_id}.question")
            _exact_keys(
                question_data,
                {"prompt", "choices", "correct"} | ({"figure"} if "figure" in question_data else set()),
                path,
                f"{item_id}.question",
            )
            prompt = _str(question_data["prompt"], path, f"{item_id}.question.prompt")
            choices = _mapping(
                question_data["choices"], path, f"{item_id}.question.choices"
            )
            _exact_keys(choices, _CHOICE_LABELS, path, f"{item_id}.question.choices")
            choice_a = _str(choices["A"], path, f"{item_id}.question.choices.A")
            choice_b = _str(choices["B"], path, f"{item_id}.question.choices.B")
            correct = _str(
                question_data["correct"], path, f"{item_id}.question.correct"
            )
            if correct not in _CHOICE_LABELS:
                _fail(path, f"{item_id}.question.correct must be A or B")
            if not prompt.endswith(_QUESTION_PROMPT_SUFFIX):
                _fail(path, f"{item_id}.question.prompt must ask which conclusion is correct")
            if any(phrase in prompt for phrase in _QUESTION_FORBIDDEN):
                _fail(path, f"{item_id}.question.prompt uses a forbidden question form")
            normalized_prompt = unicodedata.normalize("NFKC", prompt)
            if any(cue in normalized_prompt for cue in _ANSWER_CUE_FORBIDDEN) or any(
                cue in normalized_prompt for cue in _ANSWER_SYMBOL_CUES
            ):
                _fail(path, f"{item_id}.question.prompt reveals the answer")
            if _contains_invisible(prompt):
                _fail(path, f"{item_id}.question.prompt contains invisible characters")
            normalized_choices = {
                _normalized_choice(choice)
                for choice in (choice_a, choice_b)
            }
            if len(normalized_choices) != 2:
                _fail(path, f"{item_id}.question choices must be distinct")
            if max(len(choice_a), len(choice_b)) > 40:
                _fail(path, f"{item_id}.question choices must be 40 characters or fewer")
            if abs(len(choice_a) - len(choice_b)) > 10:
                _fail(path, f"{item_id}.question choices must be similar in length")
            choice_text = f"{choice_a} {choice_b}"
            if any(clue in choice_text for clue in _CHOICE_FORBIDDEN):
                _fail(path, f"{item_id}.question choices contain a forbidden clue")
            normalized_choice_text = unicodedata.normalize("NFKC", choice_text)
            if (
                any(cue in normalized_choice_text for cue in _ANSWER_CUE_FORBIDDEN)
                or any(cue in normalized_choice_text for cue in _ANSWER_SYMBOL_CUES)
                or choice_a.strip() in {"○", "×"}
                or choice_b.strip() in {"○", "×"}
            ):
                _fail(path, f"{item_id}.question choices reveal the answer")
            if _contains_invisible(choice_text):
                _fail(path, f"{item_id}.question choices contain invisible characters")
            from principle_catalog.figures import FIGURE_IDS

            figure = question_data.get("figure")
            if figure is not None and (not isinstance(figure, str) or figure not in FIGURE_IDS):
                _fail(path, f"{item_id}.question.figure must be a known versioned figure")
            question = BinaryQuestion(
                prompt=prompt,
                choice_a=choice_a,
                choice_b=choice_b,
                correct=cast(ChoiceLabel, correct),
                figure=figure,
            )
        if status == "source_checked" and question is None:
            _fail(path, f"{item_id}.question is required for source_checked entries")
        if status != "source_checked" and question is not None:
            _fail(path, f"{item_id}.question is only allowed for source_checked entries")

        reason = _str(item["reason"], path, f"{item_id}.reason")
        conditions = _string_list(item["conditions"], path, f"{item_id}.conditions")
        if not conditions:
            _fail(path, f"{item_id}.conditions must not be empty")
        if status == "source_checked" and (
            (item_type == "principle" and reason == _GAP) or _GAP in conditions
        ):
            _fail(path, f"{item_id} cannot be source_checked with a source gap")

        source = _mapping(item["source"], path, f"{item_id}.source")
        source_keys = {"pages", "question_codes"}
        if "authoritative_sources" in source:
            source_keys.add("authoritative_sources")
        _exact_keys(source, source_keys, path, f"{item_id}.source")
        pages = tuple(
            _int(page, path, f"{item_id}.source.pages entry")
            for page in _list(source["pages"], path, f"{item_id}.source.pages")
        )
        if tuple(sorted(set(pages))) != pages:
            _fail(path, f"{item_id}.source.pages must be unique and sorted")
        if any(page < manifest.first_page or page > manifest.last_page for page in pages):
            _fail(path, f"{item_id}.source.pages falls outside the audited range")
        question_codes = _string_list(
            source["question_codes"], path, f"{item_id}.source.question_codes"
        )
        if any(not _QUESTION_CODE.fullmatch(code) for code in question_codes):
            _fail(path, f"{item_id} has an invalid question code")
        authoritative_sources = (
            _load_authoritative_sources(
                source["authoritative_sources"],
                path,
                f"{item_id}.source.authoritative_sources",
            )
            if "authoritative_sources" in source
            else ()
        )
        if not pages:
            supported = {
                claim for reference in authoritative_sources for claim in reference.supports
            }
            if supported != _SOURCE_SUPPORTS or "verification" not in item:
                _fail(
                    path,
                    f"{item_id}: without audited steel pages, explicit verification and "
                    "authoritative support for statement, explanation, and conditions are required",
                )

        verification = (
            _load_verification(
                item["verification"], path, f"{item_id}.verification"
            )
            if "verification" in item
            else _default_verification(status)
        )
        if status == "source_checked" and verification != ContentVerification(
            "verified", "complete", "complete"
        ):
            _fail(
                path,
                f"{item_id}.verification must be fully verified for source_checked",
            )
        display_content = (
            _load_display_content(
                item["display_content"],
                item_type,
                path,
                f"{item_id}.display_content",
            )
            if "display_content" in item
            else None
        )
        if (
            status == "source_checked"
            and item_type in {"rule", "identification"}
            and display_content is None
        ):
            _fail(
                path,
                f"{item_id}.display_content is required for published {item_type}",
            )
        if status == "source_checked" and display_content is not None:
            # Publication verifies the fields actually taught. A regulation needs
            # its applicability, not an invented causal explanation in legacy reason.
            if isinstance(display_content, RuleDisplayContent):
                required_content = (display_content.rule, *display_content.applicability)
                qualifiers = display_content.numbers_exceptions
                has_context = bool(display_content.applicability)
            else:
                required_content = (
                    display_content.definition,
                    *display_content.distinguishing_conditions,
                )
                qualifiers = display_content.confusable_points
                has_context = bool(display_content.distinguishing_conditions)
            if not has_context or any(_GAP in value for value in (*required_content, *qualifiers)):
                _fail(path, f"{item_id}.display_content cannot have missing evidence")
            if reason == _GAP and "verification" not in item:
                _fail(path, f"{item_id} requires explicit typed verification")

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
                question=question,
                conclusion=_str(item["conclusion"], path, f"{item_id}.conclusion"),
                reason=reason,
                conditions=conditions,
                source=SourceRef(
                    pages=pages,
                    question_codes=question_codes,
                    authoritative_sources=authoritative_sources,
                ),
                prerequisites=_string_list(
                    item["prerequisites"], path, f"{item_id}.prerequisites"
                ),
                editorial_status=cast(EditorialStatus, status),
                related=(
                    _string_list(item["related"], path, f"{item_id}.related")
                    if "related" in item
                    else ()
                ),
                display_content=display_content,
                verification=verification,
            )
        )
    return tuple(principles)


def _load_taxonomy(path: Path) -> TaxonomyProjection:
    data = _load_yaml(path)
    _exact_keys(
        data,
        {"version", "display_schema", "groups", "assignments"},
        path,
        "taxonomy",
    )
    if _int(data["version"], path, "version") != 1:
        _fail(path, "version must be 1")

    raw_display = _mapping(data["display_schema"], path, "display_schema")
    _exact_keys(raw_display, {"source_fields", "types"}, path, "display_schema")
    source_fields = _mapping(
        raw_display["source_fields"], path, "display_schema.source_fields"
    )
    _exact_keys(
        source_fields,
        {"primary", "rationale", "qualifiers"},
        path,
        "display_schema.source_fields",
    )
    field_values = {
        name: _str(
            source_fields[name], path, f"display_schema.source_fields.{name}"
        )
        for name in ("primary", "rationale", "qualifiers")
    }
    if field_values != {
        "primary": "conclusion",
        "rationale": "reason",
        "qualifiers": "conditions",
    }:
        _fail(path, "display_schema.source_fields must map canonical content fields")

    raw_types = _mapping(raw_display["types"], path, "display_schema.types")
    _exact_keys(raw_types, _TYPES, path, "display_schema.types")
    expected_labels = {
        "principle": ("結論", "理由", "結論を左右する条件"),
        "rule": ("規定", "適用範囲", "数値・例外"),
        "identification": ("定義", "識別条件", "混同注意"),
    }
    type_labels: dict[PrincipleType, TypeDisplayLabels] = {}
    for item_type in sorted(_TYPES):
        labels = _mapping(
            raw_types[item_type], path, f"display_schema.types.{item_type}"
        )
        _exact_keys(
            labels,
            {"primary_label", "rationale_label", "qualifiers_label"},
            path,
            f"display_schema.types.{item_type}",
        )
        actual_labels = (
            _str(
                labels["primary_label"],
                path,
                f"display_schema.types.{item_type}.primary_label",
            ),
            _str(
                labels["rationale_label"],
                path,
                f"display_schema.types.{item_type}.rationale_label",
            ),
            _str(
                labels["qualifiers_label"],
                path,
                f"display_schema.types.{item_type}.qualifiers_label",
            ),
        )
        if actual_labels != expected_labels[item_type]:
            _fail(path, f"display_schema.types.{item_type} labels are not canonical")
        type_labels[cast(PrincipleType, item_type)] = TypeDisplayLabels(
            primary_label=actual_labels[0],
            rationale_label=actual_labels[1],
            qualifiers_label=actual_labels[2],
        )
    display_schema = DisplaySchema(
        primary_field=field_values["primary"],
        rationale_field=field_values["rationale"],
        qualifiers_field=field_values["qualifiers"],
        types=type_labels,
    )

    groups: list[TaxonomyGroup] = []
    group_ids: set[str] = set()
    subtopic_ids: set[str] = set()
    for group_index, raw_group in enumerate(
        _list(data["groups"], path, "groups"), start=1
    ):
        group_label = f"groups[{group_index}]"
        group = _mapping(raw_group, path, group_label)
        _exact_keys(group, {"id", "title", "order", "subtopics"}, path, group_label)
        group_id = _str(group["id"], path, f"{group_label}.id")
        if not _TAXONOMY_ID.fullmatch(group_id):
            _fail(path, f"invalid taxonomy group id: {group_id}")
        if group_id in group_ids:
            _fail(path, f"duplicate taxonomy group id: {group_id}")
        group_ids.add(group_id)
        group_order = _int(group["order"], path, f"{group_label}.order")
        if group_order != group_index:
            _fail(path, "taxonomy groups must be listed in contiguous order")

        subtopics: list[TaxonomySubtopic] = []
        for subtopic_index, raw_subtopic in enumerate(
            _list(group["subtopics"], path, f"{group_label}.subtopics"), start=1
        ):
            subtopic_label = f"{group_label}.subtopics[{subtopic_index}]"
            subtopic = _mapping(raw_subtopic, path, subtopic_label)
            _exact_keys(
                subtopic, {"id", "title", "order"}, path, subtopic_label
            )
            subtopic_id = _str(subtopic["id"], path, f"{subtopic_label}.id")
            if not _TAXONOMY_ID.fullmatch(subtopic_id):
                _fail(path, f"invalid taxonomy subtopic id: {subtopic_id}")
            if subtopic_id in subtopic_ids or subtopic_id in group_ids:
                _fail(path, f"duplicate taxonomy id: {subtopic_id}")
            subtopic_ids.add(subtopic_id)
            subtopic_order = _int(
                subtopic["order"], path, f"{subtopic_label}.order"
            )
            if subtopic_order != subtopic_index:
                _fail(path, "taxonomy subtopics must be listed in contiguous order")
            subtopics.append(
                TaxonomySubtopic(
                    id=subtopic_id,
                    title=_str(subtopic["title"], path, f"{subtopic_label}.title"),
                    order=subtopic_order,
                )
            )
        if not subtopics:
            _fail(path, f"{group_label}.subtopics must not be empty")
        groups.append(
            TaxonomyGroup(
                id=group_id,
                title=_str(group["title"], path, f"{group_label}.title"),
                order=group_order,
                subtopics=tuple(subtopics),
            )
        )
    # The audited projection fixes the release's tree. The schema must also
    # support new, source-verified fields such as composite and seismic design.
    if not groups:
        _fail(path, "taxonomy must contain at least one group")

    raw_assignments = _mapping(data["assignments"], path, "assignments")
    assignments: dict[str, str] = {}
    for key, raw_subtopic_id in raw_assignments.items():
        if not _ID.fullmatch(key):
            _fail(path, f"assignments has invalid principle key: {key}")
        subtopic_id = _str(raw_subtopic_id, path, f"assignments.{key}")
        if subtopic_id not in subtopic_ids:
            _fail(path, f"assignments.{key} has unknown subtopic: {subtopic_id}")
        assignments[key] = subtopic_id
    unused_subtopics = sorted(subtopic_ids - set(assignments.values()))
    if unused_subtopics:
        _fail(path, f"taxonomy subtopics without assignments: {unused_subtopics}")
    return TaxonomyProjection(
        display_schema=display_schema,
        groups=tuple(groups),
        assignments=assignments,
    )


def _load_identity_registry(path: Path) -> IdentityRegistry:
    data = _load_yaml(path)
    _exact_keys(data, {"version", "active", "retired"}, path, "identities")
    if _int(data["version"], path, "version") != 1:
        _fail(path, "version must be 1")

    def load_group(name: str) -> dict[str, PrincipleIdentity]:
        raw_group = _mapping(data[name], path, name)
        identities: dict[str, PrincipleIdentity] = {}
        for key, raw_identity in raw_group.items():
            if not _ID.fullmatch(key):
                _fail(path, f"{name} has invalid principle key: {key}")
            identity = _mapping(raw_identity, path, f"{name}.{key}")
            _exact_keys(identity, {"code", "aliases"}, path, f"{name}.{key}")
            code = _str(identity["code"], path, f"{name}.{key}.code")
            if not _PUBLIC_CODE.fullmatch(code):
                _fail(path, f"{name}.{key}.code is not a public steel code")
            aliases = _string_list(
                identity["aliases"], path, f"{name}.{key}.aliases"
            )
            if any(_contains_invisible(alias) for alias in aliases):
                _fail(path, f"{name}.{key}.aliases contain invisible characters")
            identities[key] = PrincipleIdentity(key=key, code=code, aliases=aliases)
        return identities

    active = load_group("active")
    retired = load_group("retired")
    overlapping = sorted(set(active) & set(retired))
    if overlapping:
        _fail(path, f"identity keys cannot be active and retired: {overlapping}")
    codes = [identity.code for identity in (*active.values(), *retired.values())]
    if len(codes) != len(set(codes)):
        _fail(path, "public principle codes must be unique")
    return IdentityRegistry(active=active, retired=retired)


def _load_migration_registry(path: Path) -> MigrationRegistry:
    data = _load_yaml(path)
    _exact_keys(data, {"version", "aliases", "retired"}, path, "migration")
    if _int(data["version"], path, "version") != 1:
        _fail(path, "version must be 1")

    aliases: dict[str, tuple[str, ...]] = {}
    for identifier, raw_targets in _mapping(data["aliases"], path, "aliases").items():
        if not identifier.strip() or _contains_invisible(identifier):
            _fail(path, "migration alias identifiers must be visible non-empty strings")
        targets = _string_list(raw_targets, path, f"aliases.{identifier}")
        if not targets or any(not _ID.fullmatch(target) for target in targets):
            _fail(path, f"aliases.{identifier} must contain principle keys")
        aliases[identifier] = targets

    retired: dict[str, MigrationRecord] = {}
    for key, raw_record in _mapping(data["retired"], path, "retired").items():
        if not _ID.fullmatch(key):
            _fail(path, f"retired has invalid principle key: {key}")
        record = _mapping(raw_record, path, f"retired.{key}")
        _exact_keys(
            record,
            {"operation", "targets", "progress_policy", "legacy_section"},
            path,
            f"retired.{key}",
        )
        operation = _str(record["operation"], path, f"retired.{key}.operation")
        if operation not in _MIGRATION_OPERATIONS:
            _fail(path, f"retired.{key}.operation is not supported")
        targets = _string_list(record["targets"], path, f"retired.{key}.targets")
        if operation == "split" and len(targets) < 2:
            _fail(path, f"retired.{key} split must have multiple targets")
        if operation != "split" and len(targets) != 1:
            _fail(path, f"retired.{key} {operation} must have one target")
        if any(not _ID.fullmatch(target) for target in targets):
            _fail(path, f"retired.{key}.targets must contain principle keys")
        progress_policy = _str(
            record["progress_policy"], path, f"retired.{key}.progress_policy"
        )
        if progress_policy not in _PROGRESS_POLICIES:
            _fail(path, f"retired.{key}.progress_policy is not supported")
        if operation == "split" and progress_policy != "reset_targets_to_unstarted":
            _fail(path, f"retired.{key} split targets must reset to unstarted")
        if operation == "merge" and progress_policy != "preserve_active_target_only":
            _fail(path, f"retired.{key} merge must preserve only the active target")
        legacy_section = _str(
            record["legacy_section"], path, f"retired.{key}.legacy_section"
        )
        if not _SECTION_ID.fullmatch(legacy_section):
            _fail(path, f"retired.{key}.legacy_section is not a steel section id")
        retired[key] = MigrationRecord(
            operation=cast(MigrationOperation, operation),
            targets=targets,
            progress_policy=progress_policy,
            legacy_section=legacy_section,
        )
    return MigrationRegistry(aliases=aliases, retired=retired)


def _question_edition_sha256(assignments: dict[str, int]) -> str:
    canonical = json.dumps(
        [
            {"key": key, "number": number}
            for key, number in sorted(assignments.items(), key=lambda item: item[1])
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _load_question_editions(path: Path) -> QuestionEditionRegistry:
    data = _load_yaml(path)
    _exact_keys(data, {"version", "current", "editions"}, path, "question editions")
    if _int(data["version"], path, "version") != 1:
        _fail(path, "version must be 1")
    current = _str(data["current"], path, "current")
    raw_editions = _mapping(data["editions"], path, "editions")
    editions: dict[str, QuestionEdition] = {}
    for edition_id, raw_edition in raw_editions.items():
        if not _EDITION_ID.fullmatch(edition_id):
            _fail(path, f"invalid question edition id: {edition_id}")
        edition = _mapping(raw_edition, path, f"editions.{edition_id}")
        _exact_keys(
            edition,
            {"status", "content_sha256", "assignments"},
            path,
            f"editions.{edition_id}",
        )
        status = _str(edition["status"], path, f"editions.{edition_id}.status")
        if status not in _QUESTION_EDITION_STATUSES:
            _fail(path, f"editions.{edition_id}.status is not supported")
        assignments: dict[str, int] = {}
        for key, raw_number in _mapping(
            edition["assignments"], path, f"editions.{edition_id}.assignments"
        ).items():
            if not _ID.fullmatch(key):
                _fail(path, f"editions.{edition_id} has invalid principle key: {key}")
            number = _int(
                raw_number, path, f"editions.{edition_id}.assignments.{key}"
            )
            if number < 1:
                _fail(path, f"editions.{edition_id} numbers must be positive")
            assignments[key] = number
        numbers = sorted(assignments.values())
        if numbers != list(range(1, len(assignments) + 1)):
            _fail(path, f"editions.{edition_id} numbers must be unique and contiguous")
        digest = _str(
            edition["content_sha256"],
            path,
            f"editions.{edition_id}.content_sha256",
        )
        if not _SHA256.fullmatch(digest):
            _fail(path, f"editions.{edition_id}.content_sha256 must be a SHA-256")
        if _question_edition_sha256(assignments) != digest:
            _fail(path, f"editions.{edition_id} differs from its audited snapshot")
        editions[edition_id] = QuestionEdition(
            id=edition_id,
            status=cast(QuestionEditionStatus, status),
            content_sha256=digest,
            assignments=assignments,
        )
    if current not in editions:
        _fail(path, f"current question edition does not exist: {current}")
    current_statuses = [
        edition.id for edition in editions.values() if edition.status == "current"
    ]
    if current_statuses != [current]:
        _fail(path, "exactly the declared current question edition must be current")
    current_revision = int(current.removeprefix("K6-R"))
    highest_revision = max(
        int(edition_id.removeprefix("K6-R")) for edition_id in editions
    )
    if current_revision != highest_revision:
        _fail(path, "current question edition must have the highest revision number")
    return QuestionEditionRegistry(current=current, editions=editions)


def _coverage_scheme_payload(scheme: CoverageScheme) -> dict[str, Any]:
    constraints = scheme.constraints
    return {
        "constraints": {
            "tier_counts": {
                tier: constraints.tier_counts[cast(CoverageTier, tier)]
                for tier in _COVERAGE_TIERS
            },
            "answer_counts": {
                tier: {
                    label: constraints.answer_counts[cast(CoverageTier, tier)][
                        cast(ChoiceLabel, label)
                    ]
                    for label in sorted(_CHOICE_LABELS)
                }
                for tier in _COVERAGE_TIERS
            },
            "type_counts": {
                tier: {
                    item_type: constraints.type_counts[cast(CoverageTier, tier)][
                        cast(PrincipleType, item_type)
                    ]
                    for item_type in sorted(_TYPES)
                }
                for tier in _COVERAGE_TIERS
            },
            "max_same_answer_run": constraints.max_same_answer_run,
            "foundation_covers_all_published_subtopics": (
                constraints.foundation_covers_all_published_subtopics
            ),
        },
        "assignments": [
            {
                "key": key,
                "tier": assignment.tier,
                "introduction_order": assignment.introduction_order,
                "reasons": assignment.reasons,
            }
            for key, assignment in sorted(
                scheme.assignments.items(),
                key=lambda item: item[1].introduction_order,
            )
        ],
    }


def _coverage_scheme_sha256(scheme: CoverageScheme) -> str:
    canonical = json.dumps(
        _coverage_scheme_payload(scheme),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _coverage_registry_sha256(registry: CoverageRegistry) -> str:
    canonical_projection = {
        "version": 1,
        "current": registry.current,
        "tiers": [
            {
                "tier": tier,
                "slug": registry.tiers[cast(CoverageTier, tier)].slug,
                "label": registry.tiers[cast(CoverageTier, tier)].label,
            }
            for tier in _COVERAGE_TIERS
        ],
        "schemes": [
            {
                "id": scheme.id,
                "status": scheme.status,
                "content_sha256": scheme.content_sha256,
                **_coverage_scheme_payload(scheme),
            }
            for scheme in sorted(
                registry.schemes.values(),
                key=lambda item: int(item.id.removeprefix("steel-coverage-v")),
            )
        ],
    }
    canonical = json.dumps(
        canonical_projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _load_coverage_registry(path: Path) -> CoverageRegistry:
    data = _load_yaml(path)
    _exact_keys(
        data,
        {"version", "current", "tiers", "schemes"},
        path,
        "coverage tiers",
    )
    if _int(data["version"], path, "version") != 1:
        _fail(path, "version must be 1")

    current = _str(data["current"], path, "current")
    if not _COVERAGE_SCHEME_ID.fullmatch(current):
        _fail(path, f"invalid coverage scheme id: {current}")

    tiers: dict[CoverageTier, CoverageTierDefinition] = {}
    for raw_tier, raw_definition in _coverage_tier_mapping(
        data["tiers"], path, "tiers"
    ).items():
        tier = cast(CoverageTier, raw_tier)
        definition = _mapping(raw_definition, path, f"tiers.{tier}")
        _exact_keys(definition, {"slug", "label"}, path, f"tiers.{tier}")
        slug = _str(definition["slug"], path, f"tiers.{tier}.slug")
        label = _str(definition["label"], path, f"tiers.{tier}.label")
        if (slug, label) != _COVERAGE_TIER_DEFINITIONS[tier]:
            _fail(path, f"tiers.{tier} must use the canonical definition")
        tiers[tier] = CoverageTierDefinition(tier=tier, slug=slug, label=label)

    schemes: dict[str, CoverageScheme] = {}
    for scheme_id, raw_scheme in _mapping(
        data["schemes"], path, "schemes"
    ).items():
        if not _COVERAGE_SCHEME_ID.fullmatch(scheme_id):
            _fail(path, f"invalid coverage scheme id: {scheme_id}")
        scheme = _mapping(raw_scheme, path, f"schemes.{scheme_id}")
        _exact_keys(
            scheme,
            {"status", "content_sha256", "constraints", "assignments"},
            path,
            f"schemes.{scheme_id}",
        )
        status = _str(scheme["status"], path, f"schemes.{scheme_id}.status")
        if status not in _COVERAGE_SCHEME_STATUSES:
            _fail(path, f"schemes.{scheme_id}.status is not supported")

        raw_constraints = _mapping(
            scheme["constraints"], path, f"schemes.{scheme_id}.constraints"
        )
        _exact_keys(
            raw_constraints,
            {
                "tier_counts",
                "answer_counts",
                "type_counts",
                "max_same_answer_run",
                "foundation_covers_all_published_subtopics",
            },
            path,
            f"schemes.{scheme_id}.constraints",
        )

        tier_counts: dict[CoverageTier, int] = {}
        for raw_tier, raw_count in _coverage_tier_mapping(
            raw_constraints["tier_counts"],
            path,
            f"schemes.{scheme_id}.constraints.tier_counts",
        ).items():
            tier = cast(CoverageTier, raw_tier)
            count = _int(
                raw_count,
                path,
                f"schemes.{scheme_id}.constraints.tier_counts.{tier}",
            )
            if count < 1:
                _fail(path, f"schemes.{scheme_id} tier counts must be positive")
            tier_counts[tier] = count

        answer_counts: dict[CoverageTier, dict[ChoiceLabel, int]] = {}
        for raw_tier, raw_counts in _coverage_tier_mapping(
            raw_constraints["answer_counts"],
            path,
            f"schemes.{scheme_id}.constraints.answer_counts",
        ).items():
            tier = cast(CoverageTier, raw_tier)
            counts = _mapping(
                raw_counts,
                path,
                f"schemes.{scheme_id}.constraints.answer_counts.{tier}",
            )
            _exact_keys(
                counts,
                _CHOICE_LABELS,
                path,
                f"schemes.{scheme_id}.constraints.answer_counts.{tier}",
            )
            answer_counts[tier] = {
                cast(ChoiceLabel, label): _int(
                    counts[label],
                    path,
                    f"schemes.{scheme_id}.constraints.answer_counts.{tier}.{label}",
                )
                for label in sorted(_CHOICE_LABELS)
            }
            if any(count < 0 for count in answer_counts[tier].values()):
                _fail(path, f"schemes.{scheme_id} answer counts must not be negative")
            if sum(answer_counts[tier].values()) != tier_counts[tier]:
                _fail(
                    path,
                    f"schemes.{scheme_id} answer counts must equal each tier count",
                )

        type_counts: dict[CoverageTier, dict[PrincipleType, int]] = {}
        for raw_tier, raw_counts in _coverage_tier_mapping(
            raw_constraints["type_counts"],
            path,
            f"schemes.{scheme_id}.constraints.type_counts",
        ).items():
            tier = cast(CoverageTier, raw_tier)
            counts = _mapping(
                raw_counts,
                path,
                f"schemes.{scheme_id}.constraints.type_counts.{tier}",
            )
            _exact_keys(
                counts,
                _TYPES,
                path,
                f"schemes.{scheme_id}.constraints.type_counts.{tier}",
            )
            type_counts[tier] = {
                cast(PrincipleType, item_type): _int(
                    counts[item_type],
                    path,
                    f"schemes.{scheme_id}.constraints.type_counts.{tier}.{item_type}",
                )
                for item_type in sorted(_TYPES)
            }
            if any(count < 0 for count in type_counts[tier].values()):
                _fail(path, f"schemes.{scheme_id} type counts must not be negative")
            if sum(type_counts[tier].values()) != tier_counts[tier]:
                _fail(
                    path,
                    f"schemes.{scheme_id} type counts must equal each tier count",
                )

        max_same_answer_run = _int(
            raw_constraints["max_same_answer_run"],
            path,
            f"schemes.{scheme_id}.constraints.max_same_answer_run",
        )
        if not 1 <= max_same_answer_run <= 3:
            _fail(path, f"schemes.{scheme_id}.max_same_answer_run must be 1 to 3")
        foundation_coverage = raw_constraints[
            "foundation_covers_all_published_subtopics"
        ]
        if foundation_coverage is not True:
            _fail(
                path,
                "foundation_covers_all_published_subtopics must be true",
            )
        constraints = CoverageConstraints(
            tier_counts=tier_counts,
            answer_counts=answer_counts,
            type_counts=type_counts,
            max_same_answer_run=max_same_answer_run,
            foundation_covers_all_published_subtopics=foundation_coverage,
        )

        assignments: dict[str, CoverageAssignment] = {}
        for key, raw_assignment in _mapping(
            scheme["assignments"], path, f"schemes.{scheme_id}.assignments"
        ).items():
            if not _ID.fullmatch(key):
                _fail(path, f"schemes.{scheme_id} has invalid principle key: {key}")
            assignment = _mapping(
                raw_assignment,
                path,
                f"schemes.{scheme_id}.assignments.{key}",
            )
            _exact_keys(
                assignment,
                {"tier", "introduction_order", "reasons"},
                path,
                f"schemes.{scheme_id}.assignments.{key}",
            )
            raw_tier = _int(
                assignment["tier"],
                path,
                f"schemes.{scheme_id}.assignments.{key}.tier",
            )
            if raw_tier not in _COVERAGE_TIERS:
                _fail(path, f"schemes.{scheme_id}.assignments.{key}.tier is invalid")
            reasons = _string_list(
                assignment["reasons"],
                path,
                f"schemes.{scheme_id}.assignments.{key}.reasons",
            )
            if not reasons or not set(reasons) <= _COVERAGE_REASONS:
                _fail(
                    path,
                    f"schemes.{scheme_id}.assignments.{key}.reasons are invalid",
                )
            if len(reasons) != len(set(reasons)):
                _fail(
                    path,
                    f"schemes.{scheme_id}.assignments.{key}.reasons must be unique",
                )
            introduction_order = _int(
                assignment["introduction_order"],
                path,
                f"schemes.{scheme_id}.assignments.{key}.introduction_order",
            )
            if introduction_order < 1:
                _fail(path, f"schemes.{scheme_id} introduction order must be positive")
            assignments[key] = CoverageAssignment(
                tier=cast(CoverageTier, raw_tier),
                introduction_order=introduction_order,
                reasons=cast(tuple[CoverageReason, ...], reasons),
            )
        orders = sorted(item.introduction_order for item in assignments.values())
        if orders != list(range(1, len(assignments) + 1)):
            _fail(
                path,
                f"schemes.{scheme_id} introduction order must be unique and contiguous",
            )
        ordered_tiers = [
            assignment.tier
            for assignment in sorted(
                assignments.values(), key=lambda item: item.introduction_order
            )
        ]
        if ordered_tiers != sorted(ordered_tiers):
            _fail(path, f"schemes.{scheme_id} must introduce lower tiers first")

        digest = _str(
            scheme["content_sha256"],
            path,
            f"schemes.{scheme_id}.content_sha256",
        )
        if not _SHA256.fullmatch(digest):
            _fail(path, f"schemes.{scheme_id}.content_sha256 must be a SHA-256")
        parsed = CoverageScheme(
            id=scheme_id,
            status=cast(CoverageSchemeStatus, status),
            content_sha256=digest,
            constraints=constraints,
            assignments=assignments,
        )
        if _coverage_scheme_sha256(parsed) != digest:
            _fail(path, f"schemes.{scheme_id} differs from its audited snapshot")
        schemes[scheme_id] = parsed

    if current not in schemes:
        _fail(path, f"current coverage scheme does not exist: {current}")
    current_statuses = {
        scheme.id for scheme in schemes.values() if scheme.status == "current"
    }
    if current_statuses != {current}:
        _fail(path, "exactly the declared current coverage scheme must be current")
    current_revision = int(current.removeprefix("steel-coverage-v"))
    highest_revision = max(
        int(scheme_id.removeprefix("steel-coverage-v")) for scheme_id in schemes
    )
    if current_revision != highest_revision:
        _fail(path, "current coverage scheme must have the highest version")
    return CoverageRegistry(current=current, tiers=tiers, schemes=schemes)


def _display_content_payload(item: Principle) -> dict[str, Any] | None:
    if isinstance(item.display_content, RuleDisplayContent):
        return {
            "rule": item.display_content.rule,
            "applicability": item.display_content.applicability,
            "numbers_exceptions": item.display_content.numbers_exceptions,
        }
    if isinstance(item.display_content, IdentificationDisplayContent):
        return {
            "definition": item.display_content.definition,
            "distinguishing_conditions": (
                item.display_content.distinguishing_conditions
            ),
            "confusable_points": item.display_content.confusable_points,
        }
    return None


def _question_audit_sha256(principles: tuple[Principle, ...]) -> str:
    audited = [
        {
            "key": item.id,
            "type": item.type,
            "title": item.principle,
            "prompt": item.question.prompt,
            "choices": {
                "A": item.question.choice_a,
                "B": item.question.choice_b,
            },
            "correct": item.question.correct,
            "figure": item.question.figure,
            "conclusion": item.conclusion,
            "reason": item.reason,
            "conditions": item.conditions,
            "display_content": _display_content_payload(item),
            "source": {
                "pages": item.source.pages,
                "question_codes": item.source.question_codes,
                "authoritative_sources": [
                    {
                        "kind": source.kind,
                        "title": source.title,
                        "locator": source.locator,
                        "url": source.url,
                        "supports": source.supports,
                    }
                    for source in item.source.authoritative_sources
                ],
            },
            "verification": {
                "statement_source": item.verification.statement_source,
                "explanation_completeness": (
                    item.verification.explanation_completeness
                ),
                "conditions_completeness": (
                    item.verification.conditions_completeness
                ),
            },
        }
        for item in sorted(principles, key=lambda candidate: candidate.id)
        if item.editorial_status == "source_checked" and item.question is not None
    ]
    canonical = json.dumps(
        audited,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _taxonomy_audit_sha256(taxonomy: TaxonomyProjection) -> str:
    canonical_projection = {
        "display_schema": {
            "source_fields": {
                "primary": taxonomy.display_schema.primary_field,
                "rationale": taxonomy.display_schema.rationale_field,
                "qualifiers": taxonomy.display_schema.qualifiers_field,
            },
            "types": {
                item_type: {
                    "primary_label": labels.primary_label,
                    "rationale_label": labels.rationale_label,
                    "qualifiers_label": labels.qualifiers_label,
                }
                for item_type, labels in sorted(
                    taxonomy.display_schema.types.items()
                )
            },
        },
        "groups": [
            {
                "id": group.id,
                "title": group.title,
                "order": group.order,
                "subtopics": [
                    {
                        "id": subtopic.id,
                        "title": subtopic.title,
                        "order": subtopic.order,
                    }
                    for subtopic in group.subtopics
                ],
            }
            for group in taxonomy.groups
        ],
        "assignments": [
            {"key": key, "subtopic": subtopic}
            for key, subtopic in sorted(taxonomy.assignments.items())
        ],
    }
    canonical = json.dumps(
        canonical_projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _prerequisites_audit_sha256(principles: tuple[Principle, ...]) -> str:
    relationships = [
        {
            "key": item.id,
            "prerequisites": item.prerequisites,
            "related": item.related,
        }
        for item in sorted(principles, key=lambda candidate: candidate.id)
    ]
    canonical = json.dumps(
        relationships,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _identities_audit_sha256(identities: IdentityRegistry) -> str:
    canonical_projection = {
        name: [
            {
                "key": identity.key,
                "code": identity.code,
                "aliases": sorted(identity.aliases),
            }
            for identity in sorted(group.values(), key=lambda item: item.key)
        ]
        for name, group in (
            ("active", identities.active),
            ("retired", identities.retired),
        )
    }
    canonical = json.dumps(
        canonical_projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _migration_audit_sha256(migration: MigrationRegistry) -> str:
    canonical_projection = {
        "aliases": [
            {"identifier": identifier, "targets": targets}
            for identifier, targets in sorted(migration.aliases.items())
        ],
        "retired": [
            {
                "key": key,
                "operation": record.operation,
                "targets": record.targets,
                "progress_policy": record.progress_policy,
                "legacy_section": record.legacy_section,
            }
            for key, record in sorted(migration.retired.items())
        ],
    }
    canonical = json.dumps(
        canonical_projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _migration_active_leaf_routes(
    identities: IdentityRegistry,
    migration: MigrationRegistry,
    path: Path,
) -> tuple[
    dict[str, tuple[tuple[str, ...], bool]],
    dict[str, tuple[tuple[str, ...], bool]],
]:
    """Resolve routes to active leaves while preserving historical splits."""

    if set(identities.retired) != set(migration.retired):
        _fail(path, "retired migration keys must match retired identity keys")

    active = set(identities.active)
    retired = set(identities.retired)
    known = active | retired
    resolved_retired: dict[str, tuple[tuple[str, ...], bool]] = {}
    visiting: list[str] = []

    def resolve_targets(
        targets: tuple[str, ...],
        context: str,
    ) -> tuple[tuple[str, ...], bool]:
        leaves: list[str] = []
        seen: set[str] = set()
        historically_split = len(targets) > 1
        for target in targets:
            if target not in known:
                _fail(path, f"{context} has unknown migration target: {target}")
            target_leaves, target_was_split = resolve_key(target)
            historically_split = historically_split or target_was_split
            for leaf in target_leaves:
                if leaf not in seen:
                    seen.add(leaf)
                    leaves.append(leaf)
        return tuple(leaves), historically_split

    def resolve_key(key: str) -> tuple[tuple[str, ...], bool]:
        if key in active:
            return (key,), False
        cached = resolved_retired.get(key)
        if cached is not None:
            return cached
        if key in visiting:
            cycle_start = visiting.index(key)
            cycle = (*visiting[cycle_start:], key)
            _fail(path, f"migration cycle includes: {' -> '.join(cycle)}")
        visiting.append(key)
        record = migration.retired[key]
        leaves, descendant_was_split = resolve_targets(
            record.targets,
            f"retired migration {key}",
        )
        visiting.pop()
        resolved = (
            leaves,
            record.operation == "split" or descendant_was_split,
        )
        resolved_retired[key] = resolved
        return resolved

    for key in sorted(retired):
        resolve_key(key)
    resolved_aliases: dict[str, tuple[tuple[str, ...], bool]] = {
        alias: resolve_targets(targets, f"migration alias {alias!r}")
        for alias, targets in migration.aliases.items()
    }
    return resolved_retired, resolved_aliases


def _resolution_routes(
    identities: IdentityRegistry,
    migration: MigrationRegistry,
    path: Path,
) -> dict[str, tuple[tuple[str, ...], MigrationRecord | None, bool]]:
    routes: dict[str, tuple[tuple[str, ...], MigrationRecord | None, bool]] = {}
    retired_routes, alias_routes = _migration_active_leaf_routes(
        identities,
        migration,
        path,
    )

    def add(
        identifier: str,
        targets: tuple[str, ...],
        record: MigrationRecord | None,
        historically_split: bool,
    ) -> None:
        existing = routes.get(identifier)
        if existing is not None and existing[0] != targets:
            _fail(
                path,
                f"identifier {identifier!r} resolves to conflicting targets",
            )
        if existing is None:
            routes[identifier] = (targets, record, historically_split)
            return
        routes[identifier] = (
            targets,
            record if existing[1] is None and record is not None else existing[1],
            existing[2] or historically_split,
        )

    for identity in identities.active.values():
        targets = (identity.key,)
        add(identity.key, targets, None, False)
        add(identity.code, targets, None, False)
        for alias in identity.aliases:
            add(alias, targets, None, False)
    for identity in identities.retired.values():
        record = migration.retired[identity.key]
        targets, historically_split = retired_routes[identity.key]
        add(identity.key, targets, record, historically_split)
        add(identity.code, targets, record, historically_split)
        for alias in identity.aliases:
            add(alias, targets, record, historically_split)
    for alias, targets in migration.aliases.items():
        matching_record = next(
            (
                record
                for record in migration.retired.values()
                if record.targets == targets
            ),
            None,
        )
        active_leaves, historically_split = alias_routes[alias]
        add(alias, active_leaves, matching_record, historically_split)
    return routes


def resolve_principle(catalog: Catalog, identifier: str) -> PrincipleResolution:
    """Resolve an immutable key, public code, or legacy alias centrally."""

    normalized = identifier.strip()
    routes = _resolution_routes(
        catalog.identities,
        catalog.migration,
        catalog.manifest.projection_paths["migration"],
    )
    route = routes.get(normalized)
    if route is None:
        raise UnknownPrincipleIdentifier(f"unknown catalog item: {identifier}")
    targets, migration, historically_split = route
    by_id = {item.id: item for item in catalog.principles}
    return PrincipleResolution(
        identifier=normalized,
        principles=tuple(by_id[target] for target in targets),
        migration=migration,
        historically_split=historically_split,
    )


def display_facets(catalog: Catalog, item: Principle) -> CardDisplayFacets:
    """Return semantically matched labels and values for one public card.

    Unpublished rule/identification entries may not have completed typed content.
    Those entries retain the generic canonical labels instead of mislabelling the
    legacy reason or conditions as applicability or distinguishing content.
    """

    typed = item.display_content
    if isinstance(typed, RuleDisplayContent):
        labels = catalog.taxonomy.display_schema.types["rule"]
        return CardDisplayFacets(
            primary=DisplayFacet(labels.primary_label, (typed.rule,)),
            secondary=DisplayFacet(labels.rationale_label, typed.applicability),
            tertiary=DisplayFacet(
                labels.qualifiers_label, typed.numbers_exceptions
            ),
            typed=True,
        )
    if isinstance(typed, IdentificationDisplayContent):
        labels = catalog.taxonomy.display_schema.types["identification"]
        return CardDisplayFacets(
            primary=DisplayFacet(labels.primary_label, (typed.definition,)),
            secondary=DisplayFacet(
                labels.rationale_label, typed.distinguishing_conditions
            ),
            tertiary=DisplayFacet(
                labels.qualifiers_label, typed.confusable_points
            ),
            typed=True,
        )
    return CardDisplayFacets(
        primary=DisplayFacet("結論", (item.conclusion,)),
        secondary=DisplayFacet("理由", (item.reason,)),
        tertiary=DisplayFacet("結論を左右する条件", item.conditions),
        typed=item.type == "principle",
    )


def display_principles(
    catalog: Catalog,
    *,
    published_only: bool = False,
) -> tuple[Principle, ...]:
    """Return deterministic prerequisite-first order for the display taxonomy."""

    eligible = tuple(
        item
        for item in catalog.principles
        if not published_only or item.editorial_status == "source_checked"
    )
    by_id = {item.id: item for item in eligible}
    taxonomy_rank: dict[str, tuple[int, int]] = {}
    for group in catalog.taxonomy.groups:
        for subtopic in group.subtopics:
            taxonomy_rank[subtopic.id] = (group.order, subtopic.order)
    current = catalog.question_editions.editions[catalog.question_editions.current]

    def priority(key: str) -> tuple[int, int, int, int, int, str]:
        item = by_id[key]
        group_order, subtopic_order = taxonomy_rank[
            catalog.taxonomy.assignments[key]
        ]
        question_number = current.assignments.get(key, 1_000_000)
        return (
            group_order,
            subtopic_order,
            question_number,
            item.section_order,
            item.order,
            key,
        )

    remaining = {
        item.id: {
            prerequisite
            for prerequisite in item.prerequisites
            if prerequisite in by_id
        }
        for item in eligible
    }
    ordered: list[Principle] = []
    while remaining:
        ready = [
            key for key, dependencies in remaining.items() if not dependencies
        ]
        if not ready:
            raise CatalogError("catalog prerequisites do not form a display sequence")
        key = min(ready, key=priority)
        ordered.append(by_id[key])
        del remaining[key]
        for dependencies in remaining.values():
            dependencies.discard(key)
    return tuple(ordered)


def _coverage_ceiling(value: int) -> CoverageTier:
    if isinstance(value, bool) or value not in _COVERAGE_TIERS:
        raise CatalogError("coverage ceiling must be 1, 2, or 3")
    return cast(CoverageTier, value)


def coverage_assignment(
    catalog: Catalog,
    key_or_item: str | Principle,
) -> CoverageAssignment:
    """Return the current fixed coverage assignment for one published card."""

    key = key_or_item.id if isinstance(key_or_item, Principle) else key_or_item
    current = catalog.coverage.schemes[catalog.coverage.current]
    try:
        return current.assignments[key]
    except KeyError as error:
        raise CatalogError(
            f"current coverage scheme has no assignment for {key!r}"
        ) from error


def coverage_principles(
    catalog: Catalog,
    ceiling: int = 3,
    *,
    exclusive: bool = False,
) -> tuple[Principle, ...]:
    """Filter published cards by fixed coverage tier without changing display order."""

    selected_tier = _coverage_ceiling(ceiling)
    return tuple(
        item
        for item in display_principles(catalog, published_only=True)
        if (
            coverage_assignment(catalog, item).tier == selected_tier
            if exclusive
            else coverage_assignment(catalog, item).tier <= selected_tier
        )
    )


def coverage_introduction_order(
    catalog: Catalog,
    ceiling: int = 3,
) -> tuple[Principle, ...]:
    """Return cumulative coverage cards in the current introduction order."""

    selected_tier = _coverage_ceiling(ceiling)
    by_id = {item.id: item for item in catalog.principles}
    current = catalog.coverage.schemes[catalog.coverage.current]
    return tuple(
        by_id[key]
        for key, assignment in sorted(
            current.assignments.items(),
            key=lambda item: item[1].introduction_order,
        )
        if assignment.tier <= selected_tier
    )


def validate_question_edition_history(
    previous_path: Path,
    current_path: Path = QUESTION_EDITIONS_PATH,
) -> None:
    """Reject removal or reassignment of any previously issued edition."""

    previous = _load_question_editions(previous_path)
    current = _load_question_editions(current_path)
    for edition_id, past in previous.editions.items():
        present = current.editions.get(edition_id)
        if present is None or present.assignments != past.assignments:
            _fail(
                current_path,
                f"past question edition {edition_id} must not change or be removed",
            )
        if past.status == "archived" and present.status != "archived":
            _fail(
                current_path,
                f"past question edition {edition_id} must remain archived",
            )
        if past.status == "current" and present.status not in {"current", "archived"}:
            _fail(
                current_path,
                f"past question edition {edition_id} has an invalid status transition",
            )


def validate_coverage_tier_history(
    previous_path: Path,
    current_path: Path = COVERAGE_TIERS_PATH,
) -> None:
    """Preserve issued coverage schemes while allowing a new highest version."""

    previous = _load_coverage_registry(previous_path)
    current = _load_coverage_registry(current_path)
    if current.tiers != previous.tiers:
        _fail(current_path, "coverage tier definitions must not change")
    for scheme_id, past in previous.schemes.items():
        present = current.schemes.get(scheme_id)
        if present is None or (
            present.content_sha256 != past.content_sha256
            or present.constraints != past.constraints
            or present.assignments != past.assignments
        ):
            _fail(
                current_path,
                f"past coverage scheme {scheme_id} must not change or be removed",
            )
        if past.status == "archived" and present.status != "archived":
            _fail(
                current_path,
                f"past coverage scheme {scheme_id} must remain archived",
            )


def validate_identity_history(
    previous_identities_path: Path,
    previous_migration_path: Path,
    current_identities_path: Path = IDENTITIES_PATH,
    current_migration_path: Path = MIGRATION_PATH,
) -> None:
    """Preserve every published identifier and migration route across revisions."""

    previous = _load_identity_registry(previous_identities_path)
    current = _load_identity_registry(current_identities_path)
    previous_migration = _load_migration_registry(previous_migration_path)
    current_migration = _load_migration_registry(current_migration_path)
    previous_keys = set(previous.active) | set(previous.retired)
    current_keys = set(current.active) | set(current.retired)
    removed = sorted(previous_keys - current_keys)
    if removed:
        _fail(
            current_identities_path,
            f"existing identity keys must not be removed: {removed}",
        )
    previous_by_key = {**previous.active, **previous.retired}
    current_by_key = {**current.active, **current.retired}
    changed_codes = sorted(
        key
        for key, identity in previous_by_key.items()
        if current_by_key[key].code != identity.code
    )
    if changed_codes:
        _fail(
            current_identities_path,
            f"existing identity codes must not change: {changed_codes}",
        )
    removed_aliases = {
        key: sorted(set(identity.aliases) - set(current_by_key[key].aliases))
        for key, identity in previous_by_key.items()
        if set(identity.aliases) - set(current_by_key[key].aliases)
    }
    if removed_aliases:
        _fail(
            current_identities_path,
            "existing identity aliases must not be removed: "
            f"{removed_aliases}",
        )
    reactivated = sorted(set(previous.retired) - set(current.retired))
    if reactivated:
        _fail(
            current_identities_path,
            f"retired identities must remain retired: {reactivated}",
        )
    changed_alias_routes = sorted(
        alias
        for alias, targets in previous_migration.aliases.items()
        if current_migration.aliases.get(alias) != targets
    )
    if changed_alias_routes:
        _fail(
            current_migration_path,
            "existing migration alias routes must not change or be removed: "
            f"{changed_alias_routes}",
        )
    changed_retirements = sorted(
        key
        for key, record in previous_migration.retired.items()
        if current_migration.retired.get(key) != record
    )
    if changed_retirements:
        _fail(
            current_migration_path,
            "existing retired migration records must not change or be removed: "
            f"{changed_retirements}",
        )
    if set(current.retired) != set(current_migration.retired):
        _fail(
            current_migration_path,
            "retired migration keys must match retired identity keys",
        )
    _resolution_routes(current, current_migration, current_migration_path)


def _validate_current_coverage(
    coverage: CoverageRegistry,
    principles: tuple[Principle, ...],
    taxonomy: TaxonomyProjection,
    path: Path,
) -> None:
    current = coverage.schemes[coverage.current]
    by_id = {item.id: item for item in principles}
    published_ids = {
        item.id
        for item in principles
        if item.editorial_status == "source_checked" and item.question is not None
    }
    if set(current.assignments) != published_ids:
        missing = sorted(published_ids - set(current.assignments))
        extra = sorted(set(current.assignments) - published_ids)
        _fail(
            path,
            "current coverage scheme must assign every published question exactly once; "
            f"missing={missing}, extra={extra}",
        )

    actual_tier_counts = {
        cast(CoverageTier, tier): sum(
            assignment.tier == tier for assignment in current.assignments.values()
        )
        for tier in _COVERAGE_TIERS
    }
    if actual_tier_counts != current.constraints.tier_counts:
        _fail(path, "current coverage tier counts do not match their constraints")

    actual_answer_counts = {
        cast(CoverageTier, tier): {
            cast(ChoiceLabel, label): sum(
                assignment.tier == tier
                and by_id[key].question is not None
                and by_id[key].question.correct == label
                for key, assignment in current.assignments.items()
            )
            for label in sorted(_CHOICE_LABELS)
        }
        for tier in _COVERAGE_TIERS
    }
    if actual_answer_counts != current.constraints.answer_counts:
        _fail(path, "current coverage answer counts do not match their constraints")

    actual_type_counts = {
        cast(CoverageTier, tier): {
            cast(PrincipleType, item_type): sum(
                assignment.tier == tier and by_id[key].type == item_type
                for key, assignment in current.assignments.items()
            )
            for item_type in sorted(_TYPES)
        }
        for tier in _COVERAGE_TIERS
    }
    if actual_type_counts != current.constraints.type_counts:
        _fail(path, "current coverage type counts do not match their constraints")

    for key, assignment in current.assignments.items():
        for prerequisite in by_id[key].prerequisites:
            prerequisite_assignment = current.assignments[prerequisite]
            if prerequisite_assignment.tier > assignment.tier:
                _fail(
                    path,
                    f"{key} has prerequisite in a later coverage tier: {prerequisite}",
                )
            if (
                prerequisite_assignment.tier == assignment.tier
                and prerequisite_assignment.introduction_order
                >= assignment.introduction_order
            ):
                _fail(
                    path,
                    f"{key} must introduce same-tier prerequisite first: {prerequisite}",
                )

    if current.constraints.foundation_covers_all_published_subtopics:
        published_subtopics = {
            taxonomy.assignments[key] for key in current.assignments
        }
        foundation_subtopics = {
            taxonomy.assignments[key]
            for key, assignment in current.assignments.items()
            if assignment.tier == 1
        }
        if foundation_subtopics != published_subtopics:
            missing_subtopics = sorted(published_subtopics - foundation_subtopics)
            _fail(
                path,
                "foundation tier must cover every published subtopic; "
                f"missing={missing_subtopics}",
            )
        duplicate_subtopics = sorted(
            subtopic
            for subtopic in foundation_subtopics
            if sum(
                assignment.tier == 1
                and taxonomy.assignments[key] == subtopic
                for key, assignment in current.assignments.items()
            )
            != 1
        )
        if duplicate_subtopics:
            _fail(
                path,
                "foundation tier must have one representative per published subtopic; "
                f"duplicates={duplicate_subtopics}",
            )

    answers = [
        by_id[key].question.correct
        for key, _ in sorted(
            current.assignments.items(),
            key=lambda item: item[1].introduction_order,
        )
        if by_id[key].question is not None
    ]
    longest_run = 0
    current_run = 0
    previous_answer: ChoiceLabel | None = None
    for answer in answers:
        if answer == previous_answer:
            current_run += 1
        else:
            previous_answer = answer
            current_run = 1
        longest_run = max(longest_run, current_run)
    if longest_run > current.constraints.max_same_answer_run:
        _fail(
            path,
            "current coverage introduction order exceeds max_same_answer_run",
        )


def load_catalog(manifest_path: Path = MANIFEST_PATH) -> Catalog:
    manifest = _load_manifest(manifest_path)
    audit = _load_source_audit(manifest_path.parent / SOURCE_AUDIT_FILENAME, manifest)
    physical_principles = tuple(
        principle
        for section_path in manifest.section_files
        for principle in _load_section(section_path, manifest)
    )
    if not physical_principles:
        _fail(manifest_path, "catalog must contain at least one principle")

    actual_status_counts = {
        cast(EditorialStatus, status): sum(
            item.editorial_status == status for item in physical_principles
        )
        for status in sorted(_EDITORIAL_STATUSES)
    }
    if len(physical_principles) != manifest.expected_total:
        _fail(
            manifest_path,
            "inventory total mismatch: "
            f"expected {manifest.expected_total}, got {len(physical_principles)}",
        )
    if actual_status_counts != manifest.expected_status_counts:
        _fail(
            manifest_path,
            "inventory editorial status counts do not match the catalog",
        )

    ids = [item.id for item in physical_principles]
    if len(ids) != len(set(ids)):
        duplicates = sorted(item_id for item_id in set(ids) if ids.count(item_id) > 1)
        _fail(manifest_path, f"duplicate principle IDs: {duplicates}")
    known = set(ids)

    identities = _load_identity_registry(manifest.projection_paths["identities"])
    taxonomy = _load_taxonomy(manifest.projection_paths["taxonomy"])
    migration = _load_migration_registry(manifest.projection_paths["migration"])
    question_editions = _load_question_editions(
        manifest.projection_paths["question_editions"]
    )
    coverage = _load_coverage_registry(manifest.projection_paths["coverage_tiers"])
    archived_r1 = question_editions.editions.get("K6-R1")
    if archived_r1 is None or archived_r1.status != "archived":
        _fail(
            manifest.projection_paths["question_editions"],
            "K6-R1 must remain an archived question edition",
        )
    if archived_r1.assignments != manifest.print_numbers:
        _fail(
            manifest.projection_paths["question_editions"],
            "K6-R1 must preserve the permanent print registry",
        )
    if set(identities.active) != known:
        missing = sorted(known - set(identities.active))
        extra = sorted(set(identities.active) - known)
        _fail(
            manifest.projection_paths["identities"],
            f"active identities must match active catalog keys; missing={missing}, extra={extra}",
        )
    if set(taxonomy.assignments) != known:
        missing = sorted(known - set(taxonomy.assignments))
        extra = sorted(set(taxonomy.assignments) - known)
        _fail(
            manifest.projection_paths["taxonomy"],
            f"taxonomy must assign every active key exactly once; missing={missing}, extra={extra}",
        )
    retired_keys = set(migration.retired)
    if set(identities.retired) != retired_keys:
        _fail(
            manifest.projection_paths["migration"],
            "retired migration keys must match retired identity keys",
        )
    principles = tuple(
        replace(item, code=identities.active[item.id].code)
        for item in physical_principles
    )
    by_id = {item.id: item for item in principles}

    # Resolve every declared identifier once during load so collisions fail closed.
    _resolution_routes(identities, migration, manifest.projection_paths["migration"])

    known_or_retired = known | retired_keys
    unknown_print_ids = sorted(set(manifest.print_numbers) - known_or_retired)
    if unknown_print_ids:
        _fail(manifest_path, f"print registry has unknown IDs: {unknown_print_ids}")

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
        missing_related = sorted(set(item.related) - known)
        if missing_related:
            _fail(manifest_path, f"{item.id} has unknown related items: {missing_related}")
        if item.id in item.prerequisites:
            _fail(manifest_path, f"{item.id} cannot depend on itself")
        if item.id in item.related:
            _fail(manifest_path, f"{item.id} cannot relate to itself")
        overlap = sorted(set(item.prerequisites) & set(item.related))
        if overlap:
            _fail(
                manifest_path,
                f"{item.id} cannot mark items prerequisite and related: {overlap}",
            )

    visited: set[str] = set()
    visiting: set[str] = set()
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

    taxonomy_ranks: dict[str, tuple[int, int]] = {}
    for group in taxonomy.groups:
        for subtopic in group.subtopics:
            taxonomy_ranks[subtopic.id] = (group.order, subtopic.order)
    for item in principles:
        item_rank = taxonomy_ranks[taxonomy.assignments[item.id]]
        forward = sorted(
            prerequisite
            for prerequisite in item.prerequisites
            if taxonomy_ranks[taxonomy.assignments[prerequisite]] > item_rank
        )
        if forward:
            _fail(
                manifest.projection_paths["taxonomy"],
                f"{item.id} has prerequisites in a later taxonomy subtopic: {forward}",
            )

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

    for edition in question_editions.editions.values():
        unknown_edition_keys = sorted(set(edition.assignments) - known_or_retired)
        if unknown_edition_keys:
            _fail(
                manifest.projection_paths["question_editions"],
                f"{edition.id} references unknown keys: {unknown_edition_keys}",
            )
    published_ids = {
        item.id for item in sorted_principles if item.editorial_status == "source_checked"
    }
    current_edition = question_editions.editions[question_editions.current]
    if set(current_edition.assignments) != published_ids:
        missing = sorted(published_ids - set(current_edition.assignments))
        extra = sorted(set(current_edition.assignments) - published_ids)
        _fail(
            manifest.projection_paths["question_editions"],
            "current question edition must map every published active card exactly once; "
            f"missing={missing}, extra={extra}",
        )
    for item_id in published_ids:
        later_or_equal = sorted(
            prerequisite
            for prerequisite in by_id[item_id].prerequisites
            if current_edition.assignments[prerequisite]
            >= current_edition.assignments[item_id]
        )
        if later_or_equal:
            _fail(
                manifest.projection_paths["question_editions"],
                f"{current_edition.id} must number prerequisites first for "
                f"{item_id}: {later_or_equal}",
            )
    edition_keys = [
        key
        for key, _ in sorted(
            current_edition.assignments.items(), key=lambda assignment: assignment[1]
        )
    ]
    edition_taxonomy_ranks = [
        taxonomy_ranks[taxonomy.assignments[key]] for key in edition_keys
    ]
    if edition_taxonomy_ranks != sorted(edition_taxonomy_ranks):
        _fail(
            manifest.projection_paths["question_editions"],
            f"{current_edition.id} must follow taxonomy group and subtopic order",
        )

    ordered_checked_items = sorted(
        (by_id[key] for key in current_edition.assignments),
        key=lambda item: current_edition.assignments[item.id],
    )
    checked_questions = [
        item.question
        for item in ordered_checked_items
        if item.editorial_status == "source_checked" and item.question is not None
    ]
    normalized_prompts = [
        unicodedata.normalize("NFKC", question.prompt).casefold().strip()
        for question in checked_questions
    ]
    if len(normalized_prompts) != len(set(normalized_prompts)):
        _fail(manifest_path, "source-checked question prompts must be unique")
    answer_counts = {
        label: sum(question.correct == label for question in checked_questions)
        for label in _CHOICE_LABELS
    }
    if answer_counts != manifest.expected_answer_counts:
        _fail(manifest_path, "question audit answer positions do not match the catalog")
    answer_runs: list[list[ChoiceLabel]] = []
    for question in checked_questions:
        if not answer_runs or answer_runs[-1][-1] != question.correct:
            answer_runs.append([question.correct])
        else:
            answer_runs[-1].append(question.correct)
    if answer_runs and max(map(len, answer_runs)) > 3:
        _fail(manifest_path, "source-checked answer positions must not repeat over 3 times")
    if len(checked_questions) >= 8 and len(answer_runs) < len(checked_questions) // 2:
        _fail(manifest_path, "source-checked answer positions must not form a predictable pattern")
    answer_sequence = tuple(question.correct for question in checked_questions)
    if _has_repeating_answer_period(answer_sequence):
        _fail(manifest_path, "source-checked answer positions must not repeat a fixed period")
    actual_question_audit_sha256 = _question_audit_sha256(sorted_principles)
    if actual_question_audit_sha256 != manifest.question_audit_sha256:
        _fail(
            manifest_path,
            "question content differs from the independently audited snapshot",
        )
    if current_edition.content_sha256 != manifest.question_order_sha256:
        _fail(
            manifest_path,
            "question order differs from the independently audited snapshot",
        )
    if _taxonomy_audit_sha256(taxonomy) != manifest.taxonomy_audit_sha256:
        _fail(
            manifest_path,
            "taxonomy differs from the independently audited snapshot",
        )
    if (
        _prerequisites_audit_sha256(sorted_principles)
        != manifest.prerequisites_audit_sha256
    ):
        _fail(
            manifest_path,
            "prerequisites differ from the independently audited snapshot",
        )
    if _identities_audit_sha256(identities) != manifest.identities_audit_sha256:
        _fail(
            manifest.projection_paths["identities"],
            "identities differ from the independently audited snapshot",
        )
    if _migration_audit_sha256(migration) != manifest.migration_audit_sha256:
        _fail(
            manifest.projection_paths["migration"],
            "migration differs from the independently audited snapshot",
        )
    _validate_current_coverage(
        coverage,
        sorted_principles,
        taxonomy,
        manifest.projection_paths["coverage_tiers"],
    )
    if _coverage_registry_sha256(coverage) != manifest.coverage_tiers_audit_sha256:
        _fail(
            manifest.projection_paths["coverage_tiers"],
            "coverage tiers differ from the independently audited snapshot",
        )
    return Catalog(
        manifest=manifest,
        audit=audit,
        principles=sorted_principles,
        taxonomy=taxonomy,
        identities=identities,
        migration=migration,
        question_editions=question_editions,
        coverage=coverage,
    )


def validate_print_registry_history(
    previous_manifest_path: Path,
    current_manifest_path: Path = MANIFEST_PATH,
) -> None:
    # Compare the legacy registry before cross-validating K6-R1 so this command
    # reports the history violation it was explicitly asked to audit.
    current = _load_manifest(current_manifest_path)
    previous_data = _load_yaml(previous_manifest_path)
    if "print_registry" in previous_data:
        previous_next, previous_numbers, _ = _parse_print_registry(
            previous_data["print_registry"],
            previous_manifest_path,
        )
    else:
        previous_next = 1
        previous_numbers = {}

    changed = sorted(
        item_id
        for item_id, number in previous_numbers.items()
        if current.print_numbers.get(item_id) != number
    )
    if changed:
        _fail(
            current_manifest_path,
            f"existing print numbers must not change or be removed: {changed}",
        )

    new_ids = set(current.print_numbers) - set(previous_numbers)
    current_principles = tuple(
        principle
        for section_path in current.section_files
        for principle in _load_section(section_path, current)
    )
    source_checked_ids = {
        item.id
        for item in current_principles
        if item.editorial_status == "source_checked"
    }
    unpublished_new_ids = sorted(new_ids - source_checked_ids)
    if unpublished_new_ids:
        _fail(
            current_manifest_path,
            "new print numbers may only be assigned to source-checked items: "
            f"{unpublished_new_ids}",
        )
    new_numbers = sorted(current.print_numbers[item_id] for item_id in new_ids)
    expected_new_numbers = list(range(previous_next, current.next_print_number))
    if new_numbers != expected_new_numbers:
        _fail(
            current_manifest_path,
            "new print numbers must append from the previous next_number",
        )
    load_catalog(current_manifest_path)


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
