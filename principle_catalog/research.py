"""Validated research-query snapshots for provisional catalog cards."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from principle_catalog.catalog import (
    CatalogError,
    _exact_keys,
    _int,
    _list,
    _load_yaml,
    _mapping,
    _str,
)
from principle_catalog.models import Catalog


RESEARCH_QUERIES_PATH = Path("data/principles/steel/research-queries.yaml")
_GOOGLE_SEARCH_ORIGIN = "https://www.google.com/search"
_RESEARCH_ITEM_FIELDS = {"code", "query_history"}
_QUERY_REVISION_FIELDS = {"revision", "authoritative", "explanation"}
_FORBIDDEN_QUERY_FRAGMENTS = (
    "/Users/",
    "file://",
    ".study",
    "2026_構造_文章問題.pdf",
    "S-K6-",
    "structure.steel.",
)


@dataclass(frozen=True)
class ResearchQueryPair:
    authoritative: str
    explanation: str


@dataclass(frozen=True)
class ResearchQueryRevision:
    revision: int
    authoritative: str
    explanation: str


@dataclass(frozen=True)
class ResearchQueryRecord:
    code: str
    query_history: tuple[ResearchQueryRevision, ...]

    @property
    def current(self) -> ResearchQueryPair:
        latest = self.query_history[-1]
        return ResearchQueryPair(
            authoritative=latest.authoritative,
            explanation=latest.explanation,
        )

    @property
    def authoritative(self) -> str:
        return self.query_history[-1].authoritative

    @property
    def explanation(self) -> str:
        return self.query_history[-1].explanation


@dataclass(frozen=True)
class ResearchQueryRegistry:
    version: int
    items: dict[str, ResearchQueryRecord]


def _research_query(
    value: object,
    *,
    path: Path,
    label: str,
    forbidden_question_codes: set[str],
) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise CatalogError(f"{path}: {label} must be a trimmed string")
    query = _str(value, path, label)
    if len(query) > 120:
        raise CatalogError(f"{path}: {label} must be at most 120 characters")
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in query):
        raise CatalogError(f"{path}: {label} must not contain control characters")
    if "\n" in query or "\r" in query:
        raise CatalogError(f"{path}: {label} must be a single line")
    if any(fragment.casefold() in query.casefold() for fragment in _FORBIDDEN_QUERY_FRAGMENTS):
        raise CatalogError(f"{path}: {label} exposes an internal identifier or path")
    leaked_codes = sorted(code for code in forbidden_question_codes if code in query)
    if leaked_codes:
        raise CatalogError(
            f"{path}: {label} exposes source question codes: {leaked_codes}"
        )
    if re.search(r"https?://", query, flags=re.IGNORECASE):
        raise CatalogError(f"{path}: {label} must be a search query, not a URL")
    return query


def load_research_queries(
    catalog: Catalog,
    path: Path = RESEARCH_QUERIES_PATH,
) -> ResearchQueryRegistry:
    """Load the append-only query history for every research-published route."""

    document = _load_yaml(path)
    _exact_keys(document, {"version", "items"}, path, "document")
    version = document["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise CatalogError(f"{path}: version must be 1")
    raw_items = _mapping(document["items"], path, "items")
    if not raw_items:
        raise CatalogError(f"{path}: items must not be empty")

    identities = {**catalog.identities.retired, **catalog.identities.active}
    unknown = sorted(set(raw_items) - set(identities))
    if unknown:
        raise CatalogError(
            f"{path}: research query keys are not in identity history: {unknown}"
        )
    question_codes = {
        code for item in catalog.principles for code in item.source.question_codes
    }
    items: dict[str, ResearchQueryRecord] = {}
    seen_current_queries: dict[str, str] = {}
    for key, raw_record in raw_items.items():
        record = _mapping(raw_record, path, f"items.{key}")
        _exact_keys(record, _RESEARCH_ITEM_FIELDS, path, f"items.{key}")
        code = _str(record["code"], path, f"items.{key}.code")
        if code != identities[key].code:
            raise CatalogError(
                f"{path}: {key} published code must remain {identities[key].code!r}"
            )

        raw_history = _list(
            record["query_history"], path, f"items.{key}.query_history"
        )
        if not raw_history:
            raise CatalogError(f"{path}: items.{key}.query_history must not be empty")
        history: list[ResearchQueryRevision] = []
        seen_revisions: set[tuple[str, str]] = set()
        for expected_revision, raw_revision in enumerate(raw_history, start=1):
            label = f"items.{key}.query_history[{expected_revision}]"
            revision_record = _mapping(raw_revision, path, label)
            _exact_keys(revision_record, _QUERY_REVISION_FIELDS, path, label)
            revision = _int(revision_record["revision"], path, f"{label}.revision")
            if revision != expected_revision:
                raise CatalogError(
                    f"{path}: {label}.revision must be {expected_revision}"
                )
            authoritative = _research_query(
                revision_record["authoritative"],
                path=path,
                label=f"{label}.authoritative",
                forbidden_question_codes=question_codes,
            )
            explanation = _research_query(
                revision_record["explanation"],
                path=path,
                label=f"{label}.explanation",
                forbidden_question_codes=question_codes,
            )
            normalized_authoritative = unicodedata.normalize(
                "NFKC", authoritative
            ).casefold()
            normalized_explanation = unicodedata.normalize(
                "NFKC", explanation
            ).casefold()
            if normalized_authoritative == normalized_explanation:
                raise CatalogError(
                    f"{path}: {key} revision {revision} must define two distinct "
                    "search queries"
                )
            fingerprint = (normalized_authoritative, normalized_explanation)
            if fingerprint in seen_revisions:
                raise CatalogError(
                    f"{path}: {key} query history repeats revision content"
                )
            seen_revisions.add(fingerprint)
            history.append(
                ResearchQueryRevision(
                    revision=revision,
                    authoritative=authoritative,
                    explanation=explanation,
                )
            )

        current = history[-1]
        for field, query in (
            ("authoritative", current.authoritative),
            ("explanation", current.explanation),
        ):
            normalized = unicodedata.normalize("NFKC", query).casefold()
            if normalized in seen_current_queries:
                raise CatalogError(
                    f"{path}: duplicate current search query at {key}.{field}; "
                    f"already used by {seen_current_queries[normalized]}"
                )
            seen_current_queries[normalized] = f"{key}.{field}"
        items[key] = ResearchQueryRecord(
            code=code,
            query_history=tuple(history),
        )
    return ResearchQueryRegistry(version=version, items=items)


def google_search_url(query: str) -> str:
    """Build a fixed-origin Google search URL from one validated query string."""

    return f"{_GOOGLE_SEARCH_ORIGIN}?{urlencode({'q': query})}"
