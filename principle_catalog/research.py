"""Validated search-query snapshots for confirmed and provisional cards."""

from __future__ import annotations

import hashlib
import json
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
_RESEARCH_ITEM_FIELDS = {"code", "research_route_history", "query_history"}
_QUERY_REVISION_FIELDS = {"revision", "authoritative", "explanation"}
_QUERY_RELEASE_FIELDS = {
    "id",
    "revisions",
    "route_history_lengths",
    "content_sha256",
}
_QUERY_RELEASE_ID = re.compile(r"^steel-search-v([1-9][0-9]*)$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
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
    research_route_history: tuple[str, ...]
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

    @property
    def has_research_route(self) -> bool:
        return bool(self.research_route_history)


@dataclass(frozen=True)
class ResearchQueryRelease:
    id: str
    revisions: dict[str, int]
    route_history_lengths: dict[str, int]
    content_sha256: str


@dataclass(frozen=True)
class ResearchQueryRegistry:
    version: int
    items: dict[str, ResearchQueryRecord]
    releases: tuple[ResearchQueryRelease, ...]


def _release_content_sha256(
    release_id: str,
    items: dict[str, ResearchQueryRecord],
    revisions: dict[str, int],
    route_history_lengths: dict[str, int],
) -> str:
    query_rows = []
    for key in sorted(revisions):
        for revision in items[key].query_history[: revisions[key]]:
            query_rows.append(
                {
                    "key": key,
                    "code": items[key].code,
                    "revision": revision.revision,
                    "authoritative": revision.authoritative,
                    "explanation": revision.explanation,
                }
            )
    route_rows = [
        {
            "key": key,
            "code": items[key].code,
            "research_route_history": list(
                items[key].research_route_history[: route_history_lengths[key]]
            ),
        }
        for key in sorted(route_history_lengths)
    ]
    canonical = json.dumps(
        {
            "id": release_id,
            "queries": query_rows,
            "research_routes": route_rows,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


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
    """Load the append-only query history for every search-enabled route."""

    document = _load_yaml(path)
    _exact_keys(document, {"version", "releases", "items"}, path, "document")
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

        raw_route_history = _list(
            record["research_route_history"],
            path,
            f"items.{key}.research_route_history",
        )
        route_history: list[str] = []
        for index, raw_release_id in enumerate(raw_route_history, start=1):
            release_id = _str(
                raw_release_id,
                path,
                f"items.{key}.research_route_history[{index}]",
            )
            if raw_release_id != release_id or not _QUERY_RELEASE_ID.fullmatch(
                release_id
            ):
                raise CatalogError(
                    f"{path}: items.{key}.research_route_history[{index}] "
                    "must be a trimmed steel-search-vN release id"
                )
            if release_id in route_history:
                raise CatalogError(
                    f"{path}: items.{key}.research_route_history must not repeat "
                    f"{release_id}"
                )
            route_history.append(release_id)

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
            research_route_history=tuple(route_history),
            query_history=tuple(history),
        )

    raw_releases = _list(document["releases"], path, "releases")
    if not raw_releases:
        raise CatalogError(f"{path}: releases must not be empty")
    releases: list[ResearchQueryRelease] = []
    previous_revisions: dict[str, int] = {}
    previous_route_lengths: dict[str, int] = {}
    for expected_number, raw_release in enumerate(raw_releases, start=1):
        label = f"releases[{expected_number}]"
        release = _mapping(raw_release, path, label)
        _exact_keys(release, _QUERY_RELEASE_FIELDS, path, label)
        release_id = _str(release["id"], path, f"{label}.id")
        expected_id = f"steel-search-v{expected_number}"
        if release_id != expected_id:
            raise CatalogError(f"{path}: {label}.id must be {expected_id}")

        raw_revisions = _mapping(release["revisions"], path, f"{label}.revisions")
        raw_route_lengths = _mapping(
            release["route_history_lengths"],
            path,
            f"{label}.route_history_lengths",
        )
        unknown_release_keys = sorted(
            (set(raw_revisions) | set(raw_route_lengths)) - set(items)
        )
        if unknown_release_keys:
            raise CatalogError(
                f"{path}: {label} references unknown research items: "
                f"{unknown_release_keys}"
            )

        revisions: dict[str, int] = {}
        for key, raw_revision in raw_revisions.items():
            revision = _int(raw_revision, path, f"{label}.revisions.{key}")
            if revision < 1 or revision > len(items[key].query_history):
                raise CatalogError(
                    f"{path}: {label}.revisions.{key} must cover an existing "
                    "positive revision"
                )
            revisions[key] = revision

        route_lengths: dict[str, int] = {}
        for key, raw_length in raw_route_lengths.items():
            length = _int(
                raw_length,
                path,
                f"{label}.route_history_lengths.{key}",
            )
            if length < 1 or length > len(items[key].research_route_history):
                raise CatalogError(
                    f"{path}: {label}.route_history_lengths.{key} must cover an "
                    "existing positive route-history length"
                )
            route_lengths[key] = length

        dropped_revisions = sorted(set(previous_revisions) - set(revisions))
        dropped_routes = sorted(set(previous_route_lengths) - set(route_lengths))
        if dropped_revisions or dropped_routes:
            raise CatalogError(
                f"{path}: {label} cumulative watermarks must not drop prior items"
            )
        decreased_revisions = sorted(
            key
            for key, previous in previous_revisions.items()
            if revisions[key] < previous
        )
        decreased_routes = sorted(
            key
            for key, previous in previous_route_lengths.items()
            if route_lengths[key] < previous
        )
        if decreased_revisions or decreased_routes:
            raise CatalogError(
                f"{path}: {label} cumulative watermarks must not decrease"
            )
        query_advanced = revisions != previous_revisions
        route_advanced = route_lengths != previous_route_lengths
        if not query_advanced and not route_advanced:
            raise CatalogError(
                f"{path}: {label} must publish a query or research-route change"
            )

        content_sha256 = _str(
            release["content_sha256"],
            path,
            f"{label}.content_sha256",
        )
        if not _SHA256.fullmatch(content_sha256):
            raise CatalogError(
                f"{path}: {label}.content_sha256 must be a lowercase SHA-256 digest"
            )
        expected_sha256 = _release_content_sha256(
            release_id,
            items,
            revisions,
            route_lengths,
        )
        if content_sha256 != expected_sha256:
            raise CatalogError(
                f"{path}: {label} differs from its permanent release snapshot"
            )
        releases.append(
            ResearchQueryRelease(
                id=release_id,
                revisions=revisions,
                route_history_lengths=route_lengths,
                content_sha256=content_sha256,
            )
        )
        previous_revisions = revisions
        previous_route_lengths = route_lengths

    release_positions = {
        release.id: index for index, release in enumerate(releases, start=1)
    }
    for key, record in items.items():
        unknown_route_releases = sorted(
            set(record.research_route_history) - set(release_positions)
        )
        if unknown_route_releases:
            raise CatalogError(
                f"{path}: items.{key}.research_route_history references unknown "
                f"releases: {unknown_route_releases}"
            )
        positions = [
            release_positions[release_id]
            for release_id in record.research_route_history
        ]
        if positions != sorted(positions):
            raise CatalogError(
                f"{path}: items.{key}.research_route_history must follow release order"
            )

    for index, release in enumerate(releases, start=1):
        expected_route_lengths = {
            key: sum(
                release_positions[route_release] <= index
                for route_release in record.research_route_history
            )
            for key, record in items.items()
        }
        expected_route_lengths = {
            key: length
            for key, length in expected_route_lengths.items()
            if length
        }
        if release.route_history_lengths != expected_route_lengths:
            raise CatalogError(
                f"{path}: releases[{index}].route_history_lengths must match "
                "research_route_history through that release"
            )

    final_revisions = {
        key: len(record.query_history) for key, record in items.items()
    }
    final_route_lengths = {
        key: len(record.research_route_history)
        for key, record in items.items()
        if record.research_route_history
    }
    if releases[-1].revisions != final_revisions:
        raise CatalogError(
            f"{path}: final release must cover every current query revision"
        )
    if releases[-1].route_history_lengths != final_route_lengths:
        raise CatalogError(
            f"{path}: final release must cover every published research route"
        )

    active_by_key = {item.id: item for item in catalog.principles}
    missing_active_routes = sorted(
        key
        for key, record in items.items()
        if key in active_by_key
        and active_by_key[key].editorial_status != "source_checked"
        and not record.has_research_route
    )
    if missing_active_routes:
        raise CatalogError(
            f"{path}: active unconfirmed research items must have a published "
            f"research route: {missing_active_routes}"
        )

    return ResearchQueryRegistry(
        version=version,
        items=items,
        releases=tuple(releases),
    )


def google_search_url(query: str) -> str:
    """Build a fixed-origin Google search URL from one validated query string."""

    return f"{_GOOGLE_SEARCH_ORIGIN}?{urlencode({'q': query})}"
