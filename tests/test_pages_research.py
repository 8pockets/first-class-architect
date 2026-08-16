"""Contracts for the provisional evidence-research page."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from html import escape, unescape
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
import yaml

import principle_catalog.site as site_module
from principle_catalog.catalog import CatalogError, display_principles, load_catalog
from principle_catalog.models import (
    ResearchCoverageRecord,
    ResearchCoverageRevision,
    ResearchEvidence,
    ResearchIdentificationDetails,
    ResearchPrincipleDetails,
    ResearchQuestionRecord,
    ResearchQuestionRevision,
    ResearchRuleDetails,
)
from principle_catalog.research import (
    RESEARCH_QUERIES_PATH,
    ResearchQueryRecord,
    ResearchQueryRevision,
    _release_content_sha256,
    google_search_url,
    load_research_queries,
)
from principle_catalog.research_questions import (
    load_research_coverage,
    load_research_questions,
)
from principle_catalog.site import _research_page, build_site


BASE_URL = "https://8pockets.github.io/first-class-architect/"
PILOT_KEYS = (
    "S-K6-FIRE-LOAD-FIXED-PLUS-LIVE-COMBUSTIBLES",
    "S-K6-STEEL-FIRE-STRENGTH-FIREPROOFING",
    "S-K6-FIREPROOFING-REQUIRED-ABOVE-250C",
    "S-K6-FIREPROOFING-BOARD-ATTACHMENT",
    "S-K6-FIREPROOFING-CAST-IN",
    "S-K6-FIREPROOFING-PLASTER-FINISH",
    "S-K6-FIREPROOFING-SPRAY-APPLIED",
    "S-K6-OVERHEAD-CRANE-SEISMIC-WEIGHT",
)
INITIAL_PILOT_QUERY_SHA256 = (
    "85c4ce01e12b8e4b383f5d023f2c16d62ab5674a71e5495bf15c2fc80381c070"
)
INITIAL_ALL_QUERY_SHA256 = (
    "2f6aba0d55cb02e5e97f93197588dce208d0d804403680e4b07951fd00b29fbe"
)
INITIAL_RESEARCH_RELEASES = (
    (
        "steel-search-v1",
        "f79947bc249d6b978f1a1bf648ed20599916a334207e61d565a7952109c45743",
    ),
)


def _build(tmp_path: Path) -> tuple[str, str, Path]:
    output = tmp_path / "site"
    build_site(output, BASE_URL)
    root = (output / "index.html").read_text(encoding="utf-8")
    research = (output / "research/index.html").read_text(encoding="utf-8")
    return root, research, output


def _research_card(html: str, code: str) -> str:
    opening = f'<article class="research-card" id="{code}"'
    return html.split(opening, maxsplit=1)[1].split("</article>", maxsplit=1)[0]


def _root_card(html: str, code: str) -> str:
    opening = f'<article class="principle-card" id="{code}"'
    return html.split(opening, maxsplit=1)[1].split("</article>", maxsplit=1)[0]


def _explanation_search_links(
    html: str,
) -> list[tuple[str, str, str, str]]:
    return re.findall(
        r'<a class="explanation-search-button" href="([^"]+)" target="_blank"\s*'
        r'rel="([^"]+)" referrerpolicy="no-referrer"\s*'
        r'aria-label="([^"]+)"\s*'
        r'data-research-search="explanation">([^<]+)</a>',
        html,
    )


def _sample_question_and_coverage_registries(catalog):
    by_type = {
        item_type: next(
            item
            for item in catalog.principles
            if item.type == item_type and item.editorial_status != "source_checked"
        )
        for item_type in ("principle", "rule", "identification")
    }
    specifications = (
        (
            by_type["principle"],
            "provisional_answer",
            "A",
            ResearchPrincipleDetails(
                conclusion="原理の暫定結論",
                reason="原理の暫定理由",
                conditions=("原理の暫定条件",),
            ),
        ),
        (
            by_type["rule"],
            "provisional_answer",
            "B",
            ResearchRuleDetails(
                rule="規定の暫定本文",
                applicability=("規定の暫定適用範囲",),
                numbers_exceptions=("規定の暫定数値・例外",),
            ),
        ),
        (
            by_type["identification"],
            "pending",
            None,
            ResearchIdentificationDetails(
                definition="識別の暫定定義",
                distinguishing_conditions=("識別の暫定条件",),
                confusable_points=("識別の暫定混同注意",),
            ),
        ),
    )
    question_items = {}
    coverage_items = {}
    for tier, (item, state, answer, details) in enumerate(specifications, start=1):
        supports = ("details",) if answer is None else ("answer", "details")
        question_items[item.id] = ResearchQuestionRecord(
            code=item.code,
            type=item.type,
            revision_history=(
                ResearchQuestionRevision(
                    revision=1,
                    state=state,
                    prompt=f"{item.principle}について、正しい結論はどちらか。",
                    choice_a=f"{item.type}の選択肢A",
                    choice_b=f"{item.type}の選択肢B",
                    answer=answer,
                    details=details,
                    evidence=(
                        ResearchEvidence(
                            kind="ledger",
                            locator=f"既存台帳 P{tier}",
                            supports=supports,
                        ),
                        ResearchEvidence(
                            kind="codex",
                            supplement="問題文と補足説明の編集",
                            supports=("details",),
                        ),
                    ),
                ),
            ),
        )
        coverage_items[item.id] = ResearchCoverageRecord(
            code=item.code,
            revision_history=(
                ResearchCoverageRevision(
                    revision=1,
                    tier=tier,
                    reasons=(
                        {
                            1: "coverage_representative",
                            2: "standard_application",
                            3: "exception_detail",
                        }[tier],
                    ),
                ),
            ),
        )
    return (
        SimpleNamespace(items=question_items, active_keys=tuple(question_items)),
        SimpleNamespace(items=coverage_items, active_keys=tuple(coverage_items)),
    )


def _write_query_history_registry(
    path: Path,
    catalog,
    key: str,
    history: tuple[ResearchQueryRevision, ...],
) -> None:
    code = catalog.identities.active[key].code
    record = ResearchQueryRecord(
        code=code,
        research_route_history=("steel-search-v1",),
        query_history=history,
    )
    releases = []
    for revision in range(1, len(history) + 1):
        release_id = f"steel-search-v{revision}"
        revisions = {key: revision}
        route_lengths = {key: 1}
        releases.append(
            {
                "id": release_id,
                "revisions": revisions,
                "route_history_lengths": route_lengths,
                "content_sha256": _release_content_sha256(
                    release_id,
                    {key: record},
                    revisions,
                    route_lengths,
                ),
            }
        )
    document = {
        "version": 1,
        "releases": releases,
        "items": {
            key: {
                "code": code,
                "research_route_history": ["steel-search-v1"],
                "query_history": [
                    {
                        "revision": revision.revision,
                        "authoritative": revision.authoritative,
                        "explanation": revision.explanation,
                    }
                    for revision in history
                ],
            }
        },
    }
    path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _retire_research_item(
    catalog,
    key: str,
    *,
    operation: str,
    targets: tuple[str, ...],
):
    item = next(candidate for candidate in catalog.principles if candidate.id == key)
    identity = catalog.identities.active[key]
    active_identities = dict(catalog.identities.active)
    del active_identities[key]
    template = next(iter(catalog.migration.retired.values()))
    retirement = replace(
        template,
        operation=operation,
        targets=targets,
        progress_policy=(
            "reset_targets_to_unstarted"
            if operation == "split"
            else "preserve_active_target_only"
        ),
        legacy_section=item.section_id,
    )
    return replace(
        catalog,
        principles=tuple(
            candidate for candidate in catalog.principles if candidate.id != key
        ),
        taxonomy=replace(
            catalog.taxonomy,
            assignments={
                candidate_key: subtopic
                for candidate_key, subtopic in catalog.taxonomy.assignments.items()
                if candidate_key != key
            },
        ),
        identities=replace(
            catalog.identities,
            active=active_identities,
            retired={**catalog.identities.retired, key: identity},
        ),
        migration=replace(
            catalog.migration,
            retired={**catalog.migration.retired, key: retirement},
        ),
    )


def test_research_queries_preserve_the_initial_fire_special_pilot_snapshot() -> None:
    catalog = load_catalog()
    registry = load_research_queries(catalog)
    backlog = yaml.safe_load(
        Path("data/principles/steel/research-backlog.yaml").read_text(encoding="utf-8")
    )
    raw = yaml.safe_load(RESEARCH_QUERIES_PATH.read_text(encoding="utf-8"))

    assert registry.version == 1
    # The first all-item publication contains active identities only. Future retired
    # research routes should get a separate history assertion instead of weakening
    # this immutable initial snapshot.
    assert len(registry.items) == 216
    assert set(registry.items) == set(catalog.identities.active)
    assert tuple(registry.items)[: len(PILOT_KEYS)] == PILOT_KEYS
    assert set(PILOT_KEYS) <= set(registry.items)
    assert set(backlog["topic_backlog"]["keys"]) <= set(registry.items)
    assert set(raw) == {"version", "releases", "items"}
    assert all(
        set(release)
        == {"id", "revisions", "route_history_lengths", "content_sha256"}
        for release in raw["releases"]
    )
    assert all(
        set(record) == {"code", "research_route_history", "query_history"}
        for record in raw["items"].values()
    )
    assert all(
        set(revision) == {"revision", "authoritative", "explanation"}
        for record in raw["items"].values()
        for revision in record["query_history"]
    )
    identities = {**catalog.identities.retired, **catalog.identities.active}
    pending_keys = {
        item.id
        for item in catalog.principles
        if item.editorial_status != "source_checked"
    }
    route_keys = {
        key for key, record in registry.items.items() if record.has_research_route
    }
    assert route_keys == pending_keys
    assert all(
        record.research_route_history == ("steel-search-v1",)
        for key, record in registry.items.items()
        if key in pending_keys
    )
    assert all(
        record.research_route_history == ()
        for key, record in registry.items.items()
        if key not in pending_keys
    )
    assert tuple(
        (release.id, release.content_sha256) for release in registry.releases
    ) == INITIAL_RESEARCH_RELEASES
    for key, record in registry.items.items():
        assert record.code == identities[key].code
        assert tuple(revision.revision for revision in record.query_history) == tuple(
            range(1, len(record.query_history) + 1)
        )

    initial_publication = [
        {
            "key": key,
            "code": registry.items[key].code,
            "revision": registry.items[key].query_history[0].revision,
            "authoritative": registry.items[key].query_history[0].authoritative,
            "explanation": registry.items[key].query_history[0].explanation,
        }
        for key in PILOT_KEYS
    ]
    canonical = json.dumps(
        initial_publication,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == INITIAL_PILOT_QUERY_SHA256

    initial_all_items = [
        {
            "key": key,
            "code": registry.items[key].code,
            "revision": registry.items[key].query_history[0].revision,
            "authoritative": registry.items[key].query_history[0].authoritative,
            "explanation": registry.items[key].query_history[0].explanation,
        }
        for key in sorted(registry.items)
    ]
    canonical_all_items = json.dumps(
        initial_all_items,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert (
        hashlib.sha256(canonical_all_items).hexdigest()
        == INITIAL_ALL_QUERY_SHA256
    )

    all_queries = [
        query
        for pair in registry.items.values()
        for query in (pair.authoritative, pair.explanation)
    ]
    forbidden = (
        "/Users/",
        "file://",
        ".study",
        "2026_構造_文章問題.pdf",
        "S-K6-",
        "structure.steel.",
    )
    source_codes = {
        code for item in catalog.principles for code in item.source.question_codes
    }
    assert len(all_queries) == 2 * len(registry.items)
    assert len(all_queries) == len(set(query.casefold() for query in all_queries))
    assert all(query == query.strip() and "\n" not in query for query in all_queries)
    assert all(0 < len(query) <= 120 for query in all_queries)
    assert not any(fragment in query for query in all_queries for fragment in forbidden)
    assert not any(code in query for query in all_queries for code in source_codes)


def test_research_query_loader_rejects_unknown_keys_and_unsafe_queries(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    unknown = tmp_path / "unknown.yaml"
    unknown.write_text(
        "version: 1\nreleases: []\nitems:\n  S-K6-NOT-A-REAL-KEY:\n"
        "    code: structure.steel.not-a-real-key\n"
        "    research_route_history: []\n"
        "    query_history:\n"
        "    - revision: 1\n"
        "      authoritative: official source\n"
        "      explanation: plain explanation\n",
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="identity history"):
        load_research_queries(catalog, unknown)

    unsafe = tmp_path / "unsafe.yaml"
    identity = catalog.identities.active[PILOT_KEYS[0]]
    unsafe.write_text(
        f"version: 1\nreleases: []\nitems:\n  {PILOT_KEYS[0]}:\n"
        f"    code: {identity.code}\n"
        "    research_route_history: []\n"
        "    query_history:\n"
        "    - revision: 1\n"
        "      authoritative: https://example.com/source\n"
        "      explanation: plain explanation\n",
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="search query, not a URL"):
        load_research_queries(catalog, unsafe)

    reassigned = tmp_path / "reassigned.yaml"
    reassigned.write_text(
        f"version: 1\nreleases: []\nitems:\n  {PILOT_KEYS[0]}:\n"
        "    code: structure.steel.reassigned-public-code\n"
        "    research_route_history: []\n"
        "    query_history:\n"
        "    - revision: 1\n"
        "      authoritative: official source\n"
        "      explanation: plain explanation\n",
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="published code"):
        load_research_queries(catalog, reassigned)


def test_research_query_history_keeps_old_terms_and_uses_the_latest_revision(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    key = PILOT_KEYS[0]
    history = tmp_path / "history.yaml"
    _write_query_history_registry(
        history,
        catalog,
        key,
        (
            ResearchQueryRevision(
                revision=1,
                authoritative="original official fire source",
                explanation="original fire explanation",
            ),
            ResearchQueryRevision(
                revision=2,
                authoritative="revised official fire source",
                explanation="revised fire explanation",
            ),
        ),
    )

    record = load_research_queries(catalog, history).items[key]

    assert [revision.revision for revision in record.query_history] == [1, 2]
    assert record.query_history[0].authoritative == "original official fire source"
    assert record.authoritative == "revised official fire source"
    assert record.explanation == "revised fire explanation"


def test_research_release_snapshots_reject_rewrites_and_unreleased_history(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    raw = yaml.safe_load(RESEARCH_QUERIES_PATH.read_text(encoding="utf-8"))
    key = PILOT_KEYS[0]

    rewritten = tmp_path / "rewritten.yaml"
    raw["items"][key]["query_history"][0]["authoritative"] += " 改変"
    rewritten.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="permanent release snapshot"):
        load_research_queries(catalog, rewritten)

    history = tmp_path / "unreleased.yaml"
    revisions = (
        ResearchQueryRevision(1, "first official source", "first explanation"),
        ResearchQueryRevision(2, "second official source", "second explanation"),
    )
    _write_query_history_registry(history, catalog, key, revisions)
    uncovered = yaml.safe_load(history.read_text(encoding="utf-8"))
    uncovered["releases"] = uncovered["releases"][:1]
    history.write_text(
        yaml.safe_dump(uncovered, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="final release must cover"):
        load_research_queries(catalog, history)


def test_research_release_watermarks_reject_drops_decreases_and_route_removal(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    key = PILOT_KEYS[0]
    history = tmp_path / "history.yaml"
    revisions = (
        ResearchQueryRevision(1, "first official source", "first explanation"),
        ResearchQueryRevision(2, "second official source", "second explanation"),
        ResearchQueryRevision(3, "third official source", "third explanation"),
    )
    _write_query_history_registry(history, catalog, key, revisions)

    dropped = yaml.safe_load(history.read_text(encoding="utf-8"))
    dropped["releases"][1]["revisions"] = {}
    dropped_path = tmp_path / "dropped.yaml"
    dropped_path.write_text(
        yaml.safe_dump(dropped, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="must not drop"):
        load_research_queries(catalog, dropped_path)

    decreased = yaml.safe_load(history.read_text(encoding="utf-8"))
    decreased["releases"][2]["revisions"][key] = 1
    decreased_path = tmp_path / "decreased.yaml"
    decreased_path.write_text(
        yaml.safe_dump(decreased, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="must not decrease"):
        load_research_queries(catalog, decreased_path)

    current = yaml.safe_load(RESEARCH_QUERIES_PATH.read_text(encoding="utf-8"))
    current["items"][key]["research_route_history"] = []
    removed_route = tmp_path / "removed-route.yaml"
    removed_route.write_text(
        yaml.safe_dump(current, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="route-history length"):
        load_research_queries(catalog, removed_route)

    registry = load_research_queries(catalog)
    route_release = current["releases"][0]
    del route_release["route_history_lengths"][key]
    changed_items = {
        **registry.items,
        key: replace(registry.items[key], research_route_history=()),
    }
    route_release["content_sha256"] = _release_content_sha256(
        route_release["id"],
        changed_items,
        route_release["revisions"],
        route_release["route_history_lengths"],
    )
    unpublished_route = tmp_path / "unpublished-route.yaml"
    unpublished_route.write_text(
        yaml.safe_dump(current, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="active unconfirmed"):
        load_research_queries(catalog, unpublished_route)


def test_research_registry_supports_a_route_only_release(tmp_path: Path) -> None:
    catalog = load_catalog()
    key = PILOT_KEYS[0]
    code = catalog.identities.active[key].code
    record = ResearchQueryRecord(
        code=code,
        research_route_history=("steel-search-v2",),
        query_history=(
            ResearchQueryRevision(
                1,
                "route only official source",
                "route only explanation",
            ),
        ),
    )
    items = {key: record}
    first_revisions = {key: 1}
    first_routes: dict[str, int] = {}
    second_routes = {key: 1}
    document = {
        "version": 1,
        "releases": [
            {
                "id": "steel-search-v1",
                "revisions": first_revisions,
                "route_history_lengths": first_routes,
                "content_sha256": _release_content_sha256(
                    "steel-search-v1",
                    items,
                    first_revisions,
                    first_routes,
                ),
            },
            {
                "id": "steel-search-v2",
                "revisions": first_revisions,
                "route_history_lengths": second_routes,
                "content_sha256": _release_content_sha256(
                    "steel-search-v2",
                    items,
                    first_revisions,
                    second_routes,
                ),
            },
        ],
        "items": {
            key: {
                "code": code,
                "research_route_history": ["steel-search-v2"],
                "query_history": [
                    {
                        "revision": 1,
                        "authoritative": record.authoritative,
                        "explanation": record.explanation,
                    }
                ],
            }
        },
    }
    path = tmp_path / "route-only.yaml"
    path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    registry = load_research_queries(catalog, path)

    assert tuple(release.id for release in registry.releases) == (
        "steel-search-v1",
        "steel-search-v2",
    )
    assert registry.items[key].research_route_history == ("steel-search-v2",)


def test_research_page_renders_candidate_questions_with_closed_type_specific_answers() -> None:
    catalog = load_catalog()
    queries = load_research_queries(catalog)
    questions, coverage = _sample_question_and_coverage_registries(catalog)

    research = _research_page(
        BASE_URL,
        catalog,
        queries,
        questions,
        coverage,
    )

    assert research.count('<article class="research-card"') == 3
    hero = research.split(
        '<div class="hero-stats" aria-label="調査ページの項目数">', maxsplit=1
    )[1].split("</div>\n  </header>", maxsplit=1)[0]
    assert "<strong>3</strong><span>暫定問題</span>" in hero
    assert "<strong>2</strong><span>暫定正解あり</span>" in hero
    assert "<strong>1</strong><span>判定保留</span>" in hero
    assert '<select id="research-coverage-filter">' in research
    filter_values = (
        "all",
        "core-only",
        "standard-only",
        "advanced-only",
        "core+standard",
    )
    assert all(f'<option value="{value}"' in research for value in filter_values)
    assert '<strong id="research-visible-count">3</strong>' in research
    assert 'data-research-catalog-root' in research
    assert research.count('data-research-section') == 3
    assert research.count('data-research-nav-target="') == 3
    assert research.count('data-research-answer-disclosure') == 3
    assert research.count('data-research-coverage-tier="') == 3
    assert research.count('class="research-question"') == 3
    assert research.count('class="research-binary-choices"') == 3
    assert research.count('class="research-evidence"') == 3
    assert research.count('class="explanation-search-button"') == 3
    assert research.count('class="research-answer-disclosure"') == 3
    assert research.count('class="disclosure-label-closed"') == 3
    assert research.count('class="disclosure-label-open"') == 3
    assert '<details class="research-answer-disclosure" open' not in research
    assert (
        '<script src="https://8pockets.github.io/first-class-architect/'
        'assets/research.js" defer></script>'
    ) in research

    expected_labels = {
        "principle": ("暫定結論", "暫定理由", "暫定条件"),
        "rule": ("暫定規定", "暫定適用範囲", "暫定数値・例外"),
        "identification": ("暫定定義", "暫定識別条件", "暫定混同注意"),
    }
    for tier, (key, question_record) in enumerate(questions.items.items(), start=1):
        item = next(candidate for candidate in catalog.principles if candidate.id == key)
        question = question_record.current
        card = _research_card(research, item.code)
        disclosure_start = card.index(
            '<details class="research-answer-disclosure" '
            "data-research-answer-disclosure>"
        )
        disclosure_end = card.index("</details>", disclosure_start) + len("</details>")
        disclosure = card[disclosure_start:disclosure_end]
        outside_disclosure = card[:disclosure_start] + card[disclosure_end:]

        assert f'data-research-coverage-tier="{tier}"' in card
        assert f"候補層：{('骨格', '標準', '発展')[tier - 1]}" in card
        assert escape(question.prompt) in outside_disclosure
        assert escape(question.choice_a) in outside_disclosure
        assert escape(question.choice_b) in outside_disclosure
        assert 'class="research-evidence"' in outside_disclosure
        assert "既存台帳" in outside_disclosure
        assert "Codex補足（正答根拠外）" in outside_disclosure
        assert f"既存台帳 P{tier}" not in outside_disclosure
        assert "問題文と補足説明の編集" not in outside_disclosure
        assert 'class="explanation-search-button"' in outside_disclosure
        assert "<dt>" not in outside_disclosure
        assert all(
            f"<dt>{label}</dt>" in disclosure
            for label in expected_labels[item.type]
        )
        if question.answer is None:
            assert "判定保留" in outside_disclosure
            assert "判定保留の内容を見る" in disclosure
            assert "判定保留の内容を閉じる" in disclosure
            assert "暫定正解は保留中です" in disclosure
        else:
            assert "暫定正解あり" in outside_disclosure
            assert "暫定正解と内容を見る" in disclosure
            assert "暫定正解と内容を閉じる" in disclosure
            assert (
                f'<span class="research-answer-label">{question.answer}</span>'
                in disclosure
            )

    forbidden_formal_contracts = (
        'class="print-question-number"',
        "data-print-position",
        "data-progress=",
        'id="progress-filter"',
        'id="coverage-filter"',
        'class="coverage-badge',
        'id="catalog-stats"',
        "K6-R1",
        "K6-R2",
        "K6-R3",
    )
    assert not any(marker in research for marker in forbidden_formal_contracts)


def test_build_loads_research_registries_and_copies_the_interaction_asset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = load_catalog()
    questions, coverage = _sample_question_and_coverage_registries(catalog)
    monkeypatch.setattr(
        site_module,
        "load_research_questions",
        lambda actual_catalog: questions,
    )
    monkeypatch.setattr(
        site_module,
        "load_research_coverage",
        lambda actual_catalog, actual_questions: coverage,
    )

    _, research, output = _build(tmp_path)

    assert research.count('<article class="research-card"') == 3
    assert 'data-research-catalog-root' in research
    assert (output / "assets/research.js").read_text(encoding="utf-8") == (
        Path("principle_catalog/static/research.js").read_text(encoding="utf-8")
    )


def test_research_question_controls_remain_readable_and_tappable_on_mobile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = load_catalog()
    questions, coverage = _sample_question_and_coverage_registries(catalog)
    monkeypatch.setattr(
        site_module,
        "load_research_questions",
        lambda actual_catalog: questions,
    )
    monkeypatch.setattr(
        site_module,
        "load_research_coverage",
        lambda actual_catalog, actual_questions: coverage,
    )
    _, _, output = _build(tmp_path)
    css = (output / "assets/styles.css").read_text(encoding="utf-8")

    select = re.search(r"#research-coverage-filter\s*\{([^}]*)\}", css)
    disclosure = re.search(
        r"\.research-answer-disclosure\s*>\s*summary\s*\{([^}]*)\}", css
    )
    evidence = re.search(r"\.research-evidence\s*\{([^}]*)\}", css)
    choices = re.search(r"\.research-binary-choices\s*\{([^}]*)\}", css)
    disclosure_labels = re.search(
        r"\.research-answer-disclosure\[open\] \.disclosure-label-closed,\s*"
        r"\.research-answer-disclosure:not\(\[open\]\) \.disclosure-label-open\s*"
        r"\{([^}]*)\}",
        css,
    )
    permalink = re.search(r"\.research-card-source a\s*\{([^}]*)\}", css)
    light_focus = re.search(
        r"\.research-nav a:focus-visible,\s*"
        r"\.research-card-source a:focus-visible\s*\{([^}]*)\}",
        css,
    )
    assert select is not None and "min-height: 44px" in select.group(1)
    assert disclosure is not None and "min-height: 48px" in disclosure.group(1)
    assert evidence is not None and "background:" in evidence.group(1)
    assert choices is not None and "grid-template-columns:" in choices.group(1)
    assert disclosure_labels is not None
    assert "display: none" in disclosure_labels.group(1)
    assert permalink is not None
    assert "min-width: 44px" in permalink.group(1)
    assert "min-height: 44px" in permalink.group(1)
    assert light_focus is not None
    assert "outline-color: var(--blue-dark)" in light_focus.group(1)

    mobile_rules = css.split("@media (max-width: 760px)", maxsplit=1)[1].split(
        "@media (prefers-reduced-motion", maxsplit=1
    )[0]
    mobile_controls = re.search(
        r"\.research-controls\s*\{([^}]*)\}", mobile_rules
    )
    mobile_choices = re.search(
        r"\.research-binary-choices\s*\{([^}]*)\}", mobile_rules
    )
    assert mobile_controls is not None
    assert "grid-template-columns: 1fr" in mobile_controls.group(1)
    assert mobile_choices is not None
    assert "grid-template-columns: 1fr" in mobile_choices.group(1)


def test_research_page_shows_exact_provisional_content_and_keeps_root_confirmed_only(
    tmp_path: Path,
) -> None:
    root, research, output = _build(tmp_path)
    catalog = load_catalog()
    by_key = {item.id: item for item in catalog.principles}
    registry = load_research_queries(catalog)
    questions = load_research_questions(catalog)
    coverage = load_research_coverage(catalog, questions)
    active_keys = set(questions.active_keys) & set(coverage.active_keys)
    visible_keys = tuple(
        item.id
        for item in display_principles(catalog)
        if item.id in active_keys
        and item.id in registry.items
        and registry.items[item.id].has_research_route
        and item.editorial_status != "source_checked"
    )
    confirmed_query_count = sum(
        item.id in registry.items
        for item in display_principles(catalog, published_only=True)
    )

    assert {
        page.relative_to(output).as_posix() for page in output.rglob("*.html")
    } == {"index.html", "404.html", "research/index.html"}
    assert root.count('class="principle-card"') == 116
    assert root.count('class="explanation-search-button"') == confirmed_query_count
    assert f'href="{BASE_URL}research/"' in root
    assert f"根拠確認中の{len(visible_keys)}件" in root
    assert '<h2 id="research-entry-title">根拠確認中の項目を調べる</h2>' in root
    assert "根拠確認中の項目を見る" in root
    assert "耐火・特殊荷重の根拠を調べる" not in root
    assert '<meta name="robots" content="noindex,follow">' in research
    assert f'<link rel="canonical" href="{BASE_URL}research/">' in research
    assert f'href="{BASE_URL}"' in research
    assert research.count("誤り・欠落を含む可能性があります") == len(visible_keys)
    assert "Googleの検索結果は台帳の根拠ではありません" in research
    assert 'data-research-transition' not in research
    assert len(visible_keys) == 100
    assert sum(
        questions.items[key].current.state == "provisional_answer"
        for key in visible_keys
    ) == 99
    assert sum(
        questions.items[key].current.state == "pending" for key in visible_keys
    ) == 1
    assert "<strong>100</strong><span>暫定問題</span>" in research
    assert "<strong>99</strong><span>暫定正解あり</span>" in research
    assert "<strong>1</strong><span>判定保留</span>" in research
    assert "骨格のみ（5件）" in research
    assert "標準のみ（47件）" in research
    assert "発展のみ（48件）" in research
    assert "骨格＋標準（52件）" in research

    codes = re.findall(r'<article class="research-card" id="([^"]+)"', research)
    assert codes == [by_key[key].code for key in visible_keys]
    for key in visible_keys:
        item = by_key[key]
        record = questions.items[key]
        question = record.current
        card = _research_card(research, item.code)
        assert item.id not in research
        assert f'<article class="principle-card" id="{item.code}"' not in root
        assert escape(item.principle) in card
        assert record.type == item.type
        disclosure_start = card.index(
            '<details class="research-answer-disclosure" '
            "data-research-answer-disclosure>"
        )
        disclosure_end = card.index("</details>", disclosure_start) + len("</details>")
        disclosure = card[disclosure_start:disclosure_end]
        outside_disclosure = card[:disclosure_start] + card[disclosure_end:]
        assert escape(question.prompt) in outside_disclosure
        assert escape(question.choice_a) in outside_disclosure
        assert escape(question.choice_b) in outside_disclosure
        assert 'class="research-evidence"' in outside_disclosure
        assert 'class="explanation-search-button"' in outside_disclosure
        assert "候補層：" in outside_disclosure
        if isinstance(question.details, ResearchPrincipleDetails):
            expected_rows = (
                ("暫定結論", (question.details.conclusion,)),
                ("暫定理由", (question.details.reason,)),
                ("暫定条件", question.details.conditions),
            )
        elif isinstance(question.details, ResearchRuleDetails):
            expected_rows = (
                ("暫定規定", (question.details.rule,)),
                ("暫定適用範囲", question.details.applicability),
                ("暫定数値・例外", question.details.numbers_exceptions),
            )
        else:
            expected_rows = (
                ("暫定定義", (question.details.definition,)),
                ("暫定識別条件", question.details.distinguishing_conditions),
                ("暫定混同注意", question.details.confusable_points),
            )
        for label, values in expected_rows:
            assert f"<dt>{label}</dt>" in disclosure
            assert all(escape(value) in disclosure for value in values)
        for evidence in question.evidence:
            hidden_values = (evidence.locator, evidence.title, evidence.supplement)
            assert all(
                value is None or escape(value) not in outside_disclosure
                for value in hidden_values
            )
            if evidence.url:
                assert escape(evidence.url) not in outside_disclosure
        assert outside_disclosure.count("既存台帳") == sum(
            evidence.kind == "ledger" for evidence in question.evidence
        )
        assert outside_disclosure.count("外部資料確認") == sum(
            evidence.kind == "external" for evidence in question.evidence
        )
        assert outside_disclosure.count("Codex補足（正答根拠外）") == sum(
            evidence.kind == "codex" for evidence in question.evidence
        )
        assert f'href="#{item.code}"' in card


def test_research_cards_use_canonical_display_order_not_registry_order() -> None:
    catalog = load_catalog()
    registry = load_research_queries(catalog)
    questions = load_research_questions(catalog)
    coverage = load_research_coverage(catalog, questions)
    reversed_registry = replace(
        registry,
        items=dict(reversed(tuple(registry.items.items()))),
    )
    research = _research_page(
        BASE_URL,
        catalog,
        reversed_registry,
        questions,
        coverage,
    )

    actual_codes = re.findall(
        r'<article class="research-card" id="([^"]+)"',
        research,
    )
    expected_codes = [
        item.code
        for item in display_principles(catalog)
        if item.id in questions.active_keys
        and item.id in coverage.active_keys
        and item.id in registry.items
        and registry.items[item.id].has_research_route
        and item.editorial_status != "source_checked"
    ]

    assert actual_codes == expected_codes


def test_root_research_entry_is_excluded_from_the_question_sheet(
    tmp_path: Path,
) -> None:
    _, _, output = _build(tmp_path)
    css = (output / "assets/styles.css").read_text(encoding="utf-8")
    print_rules = css.split("@media print", maxsplit=1)[1]
    match = re.search(r"\.research-entry\s*\{([^}]*)\}", print_rules)

    assert match is not None
    assert "display: none !important" in match.group(1)


def test_research_page_content_is_excluded_from_print(
    tmp_path: Path,
) -> None:
    _, _, output = _build(tmp_path)
    css = (output / "assets/styles.css").read_text(encoding="utf-8")
    print_rules = css.split("@media print", maxsplit=1)[1]
    hidden = re.search(
        r"\.research-warning,\s*"
        r"\.research-controls,\s*"
        r"\.research-nav,\s*"
        r"\.research-catalog\s*\{([^}]*)\}",
        print_rules,
    )

    assert hidden is not None
    assert "display: none !important" in hidden.group(1)


def test_confirmed_card_with_queries_adds_one_always_visible_explanation_button(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = load_catalog()
    item = next(
        candidate
        for candidate in catalog.principles
        if candidate.editorial_status == "source_checked"
    )
    registry = load_research_queries(catalog)
    authoritative = "鉄骨構造 確認済み項目 一次資料 検索テスト"
    explanation = "鉄骨構造 確認済み項目 分かりやすい解説 検索テスト"
    confirmed_record = ResearchQueryRecord(
        code=item.code,
        research_route_history=(),
        query_history=(
            ResearchQueryRevision(
                revision=1,
                authoritative=authoritative,
                explanation=explanation,
            ),
        ),
    )
    changed_registry = replace(
        registry,
        items={**registry.items, item.id: confirmed_record},
    )
    monkeypatch.setattr(
        site_module,
        "load_research_queries",
        lambda actual_catalog: changed_registry,
    )

    root, _, output = _build(tmp_path)
    card = _root_card(root, item.code)
    action_opening = '<div class="explanation-search-action">'
    action = card.split(action_opening, maxsplit=1)[1].split("</div>", maxsplit=1)[0]

    assert root.count('class="principle-card"') == 116
    assert root.count('class="practice-question"') == 116
    assert root.count(
        '<details class="answer-disclosure" data-answer-disclosure>'
    ) == 116
    expected_button_count = sum(
        candidate.id in changed_registry.items
        for candidate in display_principles(catalog, published_only=True)
    )
    assert root.count(action_opening) == expected_button_count
    assert root.count('class="explanation-search-button"') == expected_button_count
    assert card.count(action_opening) == 1
    assert card.count('class="explanation-search-button"') == 1
    assert card.index("</details>") < card.index(action_opening)
    assert card.index(action_opening) < card.index('<footer class="card-source">')
    assert "<details" not in action
    assert "<summary" not in action
    assert "<code" not in action
    assert authoritative not in action
    assert "一次資料優先" not in action

    links = _explanation_search_links(action)
    assert len(links) == 1
    href, rel, accessible_name, visible_label = links[0]
    assert unescape(href) == google_search_url(explanation)
    assert set(rel.split()) == {
        "external",
        "nofollow",
        "noopener",
        "noreferrer",
    }
    assert unescape(accessible_name) == (
        f"{item.principle}：分かりやすい解説をGoogleで検索（別タブ）"
    )
    assert visible_label == "分かりやすい解説"

    print_rules = (output / "assets/styles.css").read_text(
        encoding="utf-8"
    ).split("@media print", maxsplit=1)[1]
    hidden = re.search(r"\.explanation-search-button\s*\{([^}]*)\}", print_rules)
    assert hidden is not None
    assert "display: none !important" in hidden.group(1)


def test_every_card_has_one_direct_explanation_search_and_no_visible_search_trails(
    tmp_path: Path,
) -> None:
    root, research, output = _build(tmp_path)
    catalog = load_catalog()
    by_key = {item.id: item for item in catalog.principles}
    registry = load_research_queries(catalog)
    provisional_records = {
        key: record
        for key, record in registry.items.items()
        if key in by_key
        and record.has_research_route
        and by_key[key].editorial_status != "source_checked"
    }
    confirmed_records = {
        key: record
        for key, record in registry.items.items()
        if key in by_key and by_key[key].editorial_status == "source_checked"
    }
    expected_research_queries = {
        record.explanation for record in provisional_records.values()
    }
    expected_root_queries = {
        record.explanation for record in confirmed_records.values()
    }
    expected_accessible_names = {
        record.explanation: (
            f"{by_key[key].principle}：分かりやすい解説をGoogleで検索（別タブ）"
        )
        for key, record in registry.items.items()
        if key in by_key
    }
    links = _explanation_search_links(research)
    root_links = _explanation_search_links(root)

    assert len(links) == len(provisional_records) == 100
    assert len(root_links) == len(confirmed_records) == 116
    assert len(links) + len(root_links) == 216
    assert research.count('href="https://www.google.com/search?') == 100
    assert root.count('href="https://www.google.com/search?') == 116
    for key in provisional_records:
        card = _research_card(research, by_key[key].code)
        assert card.count('class="explanation-search-button"') == 1
        assert card.index("</dl>") < card.index(
            '<div class="explanation-search-action">'
        )
        assert card.index('<div class="explanation-search-action">') < card.index(
            '<footer class="card-source research-card-source">'
        )
    for key in confirmed_records:
        card = _root_card(root, by_key[key].code)
        assert card.count('class="explanation-search-button"') == 1
    actual_research_queries = {
        parse_qs(urlsplit(unescape(href)).query, strict_parsing=True)["q"][0]
        for href, _, _, _ in links
    }
    actual_root_queries = {
        parse_qs(urlsplit(unescape(href)).query, strict_parsing=True)["q"][0]
        for href, _, _, _ in root_links
    }
    assert actual_research_queries == expected_research_queries
    assert actual_root_queries == expected_root_queries

    all_links = links + root_links
    assert len({unescape(label) for _, _, label, _ in all_links}) == 216
    for href, rel, accessible_name, visible_label in all_links:
        href = unescape(href)
        accessible_name = unescape(accessible_name)
        query = parse_qs(urlsplit(href).query, strict_parsing=True)["q"][0]
        assert accessible_name == expected_accessible_names[query]
        assert href == f"https://www.google.com/search?{urlencode({'q': query})}"
        assert href == google_search_url(query)
        assert visible_label == "分かりやすい解説"
        parsed = urlsplit(href)
        assert (parsed.scheme, parsed.netloc, parsed.path) == (
            "https",
            "www.google.com",
            "/search",
        )
        assert parse_qs(parsed.query, strict_parsing=True) == {"q": [query]}
        assert set(rel.split()) == {"external", "nofollow", "noopener", "noreferrer"}

    for html in (root, research):
        assert 'data-research-search="authoritative"' not in html
        assert 'class="reference-search"' not in html
        assert 'class="research-searches"' not in html
        assert "SEARCH TRAILS" not in html
        assert "一次資料優先" not in html
        assert "一次資料を優先して探す" not in html
    for record in registry.items.values():
        assert escape(record.authoritative) not in root
        assert escape(record.authoritative) not in research
        assert escape(record.explanation) not in root
        assert escape(record.explanation) not in research

    disclosure = (
        "「分かりやすい解説」を開くと、項目ごとの解説向け検索語がGoogleへ"
        "送信されます。Googleの検索結果は台帳の根拠ではありません。"
    )
    assert root.count(disclosure) == 1
    assert research.count(disclosure) == 1
    assert root.index(disclosure) < root.index('<section class="controls"')
    warning = research.split(
        '<section class="research-warning"', maxsplit=1
    )[1].split("</section>", maxsplit=1)[0]
    assert disclosure in warning

    css = (output / "assets/styles.css").read_text(encoding="utf-8")
    focus = re.search(
        r"\.explanation-search-button:focus-visible\s*\{([^}]*)\}",
        css,
    )
    assert focus is not None
    assert "outline: 3px solid var(--blue-dark)" in focus.group(1)
    button = re.search(r"\.explanation-search-button\s*\{([^}]*)\}", css)
    assert button is not None
    assert "min-height: 44px" in button.group(1)
    mobile_rules = css.split("@media (max-width: 760px)", maxsplit=1)[1].split(
        "@media (prefers-reduced-motion", maxsplit=1
    )[0]
    mobile_button = re.search(
        r"\.explanation-search-button\s*\{([^}]*)\}", mobile_rules
    )
    assert mobile_button is not None
    assert "width: 100%" in mobile_button.group(1)
    print_rules = css.split("@media print", maxsplit=1)[1]
    print_button = re.search(
        r"\.explanation-search-button\s*\{([^}]*)\}", print_rules
    )
    assert print_button is not None
    assert "display: none !important" in print_button.group(1)


def test_research_page_excludes_learning_and_private_state_features(
    tmp_path: Path,
) -> None:
    _, research, output = _build(tmp_path)
    forbidden_research_markup = (
        'class="practice-question"',
        'class="binary-choices"',
        'class="answer-disclosure"',
        'class="answer-key"',
        'id="toggle-visible-answers"',
        'id="progress-filter"',
        "data-progress=",
        'class="progress-badge',
        'id="coverage-filter"',
        "data-coverage-",
        'class="coverage-badge',
        'class="print-question-number"',
        "data-print-position",
        "K6-R1",
        "K6-R2",
        "K6-R3",
        'id="catalog-stats"',
        "<form",
    )
    assert not any(marker in research for marker in forbidden_research_markup)
    assert research.count("<script") == 1
    assert f'src="{BASE_URL}assets/research.js"' in research
    assert "assets/catalog.js" not in research
    for page in output.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert "/Users/" not in html
        assert ".study" not in html
        assert "2026_構造_文章問題.pdf" not in html


def test_source_checked_query_entry_keeps_a_target_only_research_route() -> None:
    catalog = load_catalog()
    questions = load_research_questions(catalog)
    coverage = load_research_coverage(catalog, questions)
    item = next(candidate for candidate in catalog.principles if candidate.id == PILOT_KEYS[0])
    checked = replace(item, editorial_status="source_checked")
    changed_catalog = replace(
        catalog,
        principles=tuple(
            checked if candidate.id == item.id else candidate
            for candidate in catalog.principles
        ),
    )
    registry = load_research_queries(changed_catalog)

    research = _research_page(
        BASE_URL,
        changed_catalog,
        registry,
        questions,
        coverage,
    )

    assert f'<article class="research-card" id="{item.code}"' not in research
    assert re.search(
        rf'<section class="research-transition legacy-route" id="{re.escape(item.code)}"\s+'
        r"data-research-transition>",
        research,
    )
    assert f'href="{BASE_URL}#{item.code}"' in research


def test_retired_research_route_follows_a_merge_to_a_confirmed_card() -> None:
    catalog = load_catalog()
    questions = load_research_questions(catalog)
    coverage = load_research_coverage(catalog, questions)
    item = next(candidate for candidate in catalog.principles if candidate.id == PILOT_KEYS[0])
    target = next(
        candidate
        for candidate in catalog.principles
        if candidate.editorial_status == "source_checked"
    )
    changed_catalog = _retire_research_item(
        catalog,
        item.id,
        operation="merge",
        targets=(target.id,),
    )
    registry = load_research_queries(changed_catalog)

    research = _research_page(
        BASE_URL,
        changed_catalog,
        registry,
        questions,
        coverage,
    )

    opening = (
        f'<section class="research-transition legacy-route" id="{item.code}" '
        'data-research-migration="merge">'
    )
    transition = research.split(opening, maxsplit=1)[1].split(
        "</section>", maxsplit=1
    )[0]
    assert item.id not in research
    assert registry.items[item.id].code == item.code
    assert registry.items[item.id].query_history[0].revision == 1
    assert "別の項目へ統合されました" in transition
    assert f'href="{BASE_URL}#{target.code}"' in transition
    assert escape(target.principle) in transition


def test_retired_research_split_exposes_only_previously_public_targets() -> None:
    catalog = load_catalog()
    questions = load_research_questions(catalog)
    coverage = load_research_coverage(catalog, questions)
    item = next(candidate for candidate in catalog.principles if candidate.id == PILOT_KEYS[1])
    confirmed = next(
        candidate
        for candidate in catalog.principles
        if candidate.editorial_status == "source_checked"
    )
    never_public = next(
        candidate
        for candidate in catalog.principles
        if candidate.editorial_status != "source_checked"
        and candidate.id not in PILOT_KEYS
        and candidate.id != item.id
    )
    changed_catalog = _retire_research_item(
        catalog,
        item.id,
        operation="split",
        targets=(confirmed.id, never_public.id),
    )
    registry = load_research_queries(changed_catalog)
    registry = replace(
        registry,
        items={
            key: (
                replace(record, research_route_history=())
                if key == never_public.id
                else record
            )
            for key, record in registry.items.items()
        },
    )

    research = _research_page(
        BASE_URL,
        changed_catalog,
        registry,
        questions,
        coverage,
    )

    opening = (
        f'<section class="research-transition legacy-route" id="{item.code}" '
        'data-research-migration="split">'
    )
    transition = research.split(opening, maxsplit=1)[1].split(
        "</section>", maxsplit=1
    )[0]
    assert "複数の項目へ分割されました" in transition
    assert f'href="{BASE_URL}#{confirmed.code}"' in transition
    assert escape(confirmed.principle) in transition
    assert 'data-unpublished-research-targets="1"' in transition
    assert never_public.id not in research
    assert never_public.code not in research
    assert escape(never_public.principle) not in research
