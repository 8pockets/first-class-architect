"""Contracts for the provisional evidence-research page."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from html import escape, unescape
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
import yaml

from principle_catalog.catalog import CatalogError, load_catalog
from principle_catalog.research import (
    RESEARCH_QUERIES_PATH,
    google_search_url,
    load_research_queries,
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


def _build(tmp_path: Path) -> tuple[str, str, Path]:
    output = tmp_path / "site"
    build_site(output, BASE_URL)
    root = (output / "index.html").read_text(encoding="utf-8")
    research = (output / "research/index.html").read_text(encoding="utf-8")
    return root, research, output


def _research_card(html: str, code: str) -> str:
    opening = f'<article class="research-card" id="{code}"'
    return html.split(opening, maxsplit=1)[1].split("</article>", maxsplit=1)[0]


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
    assert tuple(registry.items)[: len(PILOT_KEYS)] == PILOT_KEYS
    assert set(PILOT_KEYS) <= set(registry.items)
    assert set(backlog["topic_backlog"]["keys"]) <= set(registry.items)
    assert set(raw) == {"version", "items"}
    assert all(
        set(record) == {"code", "query_history"}
        for record in raw["items"].values()
    )
    assert all(
        set(revision) == {"revision", "authoritative", "explanation"}
        for record in raw["items"].values()
        for revision in record["query_history"]
    )
    identities = {**catalog.identities.retired, **catalog.identities.active}
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
        "version: 1\nitems:\n  S-K6-NOT-A-REAL-KEY:\n"
        "    code: structure.steel.not-a-real-key\n"
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
        f"version: 1\nitems:\n  {PILOT_KEYS[0]}:\n"
        f"    code: {identity.code}\n"
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
        f"version: 1\nitems:\n  {PILOT_KEYS[0]}:\n"
        "    code: structure.steel.reassigned-public-code\n"
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
    code = catalog.identities.active[key].code
    history = tmp_path / "history.yaml"
    history.write_text(
        f"version: 1\nitems:\n  {key}:\n"
        f"    code: {code}\n"
        "    query_history:\n"
        "    - revision: 1\n"
        "      authoritative: original official fire source\n"
        "      explanation: original fire explanation\n"
        "    - revision: 2\n"
        "      authoritative: revised official fire source\n"
        "      explanation: revised fire explanation\n",
        encoding="utf-8",
    )

    record = load_research_queries(catalog, history).items[key]

    assert [revision.revision for revision in record.query_history] == [1, 2]
    assert record.query_history[0].authoritative == "original official fire source"
    assert record.authoritative == "revised official fire source"
    assert record.explanation == "revised fire explanation"


def test_research_page_shows_exact_provisional_content_and_keeps_root_confirmed_only(
    tmp_path: Path,
) -> None:
    root, research, output = _build(tmp_path)
    catalog = load_catalog()
    by_key = {item.id: item for item in catalog.principles}
    registry = load_research_queries(catalog)
    visible_keys = tuple(
        key
        for key in registry.items
        if key in by_key and by_key[key].editorial_status != "source_checked"
    )

    assert {
        page.relative_to(output).as_posix() for page in output.rglob("*.html")
    } == {"index.html", "404.html", "research/index.html"}
    assert root.count('class="principle-card"') == 116
    assert f'href="{BASE_URL}research/"' in root
    assert f"根拠確認中の{len(visible_keys)}件" in root
    assert '<meta name="robots" content="noindex,follow">' in research
    assert f'<link rel="canonical" href="{BASE_URL}research/">' in research
    assert f'href="{BASE_URL}"' in research
    assert research.count("誤り・欠落を含む可能性があります") == len(visible_keys)
    assert "Googleの検索結果は台帳の根拠ではありません" in research

    codes = re.findall(r'<article class="research-card" id="([^"]+)"', research)
    assert codes == [by_key[key].code for key in visible_keys]
    for key in visible_keys:
        item = by_key[key]
        card = _research_card(research, item.code)
        assert item.id not in research
        assert item.code not in root
        assert item.principle not in root
        assert escape(item.principle) in card
        assert "<dt>暫定結論</dt>" in card
        assert escape(item.conclusion) in card
        assert "<dt>暫定理由</dt>" in card
        assert escape(item.reason) in card
        assert "<dt>暫定条件</dt>" in card
        assert all(escape(condition) in card for condition in item.conditions)
        assert f'href="#{item.code}"' in card
        pages = "・".join(f"P{page}" for page in item.source.pages)
        assert f"PDF {pages}" in card
        if item.source.question_codes:
            assert f"問題コード {'・'.join(item.source.question_codes)}" in card
        assert "既存台帳の教材内確認" in card
        assert "外部一次資料の確認結果ではありません" in card


def test_root_research_entry_is_excluded_from_the_question_sheet(
    tmp_path: Path,
) -> None:
    _, _, output = _build(tmp_path)
    css = (output / "assets/styles.css").read_text(encoding="utf-8")
    print_rules = css.split("@media print", maxsplit=1)[1]
    match = re.search(r"\.research-entry\s*\{([^}]*)\}", print_rules)

    assert match is not None
    assert "display: none !important" in match.group(1)


def test_google_links_round_trip_visible_queries_and_are_external_only(
    tmp_path: Path,
) -> None:
    _, research, output = _build(tmp_path)
    registry = load_research_queries(load_catalog())
    expected_queries = {
        query
        for pair in registry.items.values()
        for query in (pair.authoritative, pair.explanation)
    }
    links = re.findall(
        r'<code>(.*?)</code>\s*<a href="([^"]+)" target="_blank"\s*'
        r'rel="([^"]+)" referrerpolicy="no-referrer"\s*'
        r'aria-label="([^"]+)"\s*'
        r'data-research-search="(authoritative|explanation)">',
        research,
        flags=re.DOTALL,
    )

    assert len(links) == 16
    assert {unescape(query) for query, _, _, _, _ in links} == expected_queries
    assert len({unescape(label) for _, _, _, label, _ in links}) == 16
    for raw_query, href, rel, accessible_name, kind in links:
        query = unescape(raw_query)
        href = unescape(href)
        accessible_name = unescape(accessible_name)
        assert kind in {"authoritative", "explanation"}
        expected_intent = (
            "一次資料を優先して探す"
            if kind == "authoritative"
            else "分かりやすい解説を探す"
        )
        assert expected_intent in accessible_name
        assert accessible_name.endswith("Googleで検索（別タブ）")
        assert href == f"https://www.google.com/search?{urlencode({'q': query})}"
        assert href == google_search_url(query)
        parsed = urlsplit(href)
        assert (parsed.scheme, parsed.netloc, parsed.path) == (
            "https",
            "www.google.com",
            "/search",
        )
        assert parse_qs(parsed.query, strict_parsing=True) == {"q": [query]}
        assert set(rel.split()) == {"external", "nofollow", "noopener", "noreferrer"}

    css = (output / "assets/styles.css").read_text(encoding="utf-8")
    focus = re.search(
        r"\.research-search-option a:focus-visible\s*\{([^}]*)\}",
        css,
    )
    assert focus is not None
    assert "outline-color: var(--blue-dark)" in focus.group(1)


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
        "<script",
        "<form",
    )
    assert not any(marker in research for marker in forbidden_research_markup)
    for page in output.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert "/Users/" not in html
        assert ".study" not in html
        assert "2026_構造_文章問題.pdf" not in html


def test_source_checked_query_entry_keeps_a_target_only_research_route() -> None:
    catalog = load_catalog()
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

    research = _research_page(BASE_URL, changed_catalog, registry)

    assert f'<article class="research-card" id="{item.code}"' not in research
    assert re.search(
        rf'<section class="research-transition legacy-route" id="{re.escape(item.code)}"\s+'
        r"data-research-transition>",
        research,
    )
    assert f'href="{BASE_URL}#{item.code}"' in research


def test_retired_research_route_follows_a_merge_to_a_confirmed_card() -> None:
    catalog = load_catalog()
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

    research = _research_page(BASE_URL, changed_catalog, registry)

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

    research = _research_page(BASE_URL, changed_catalog, registry)

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
