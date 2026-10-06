"""Public Pages coverage-layer contracts."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from html import unescape
from pathlib import Path

from principle_catalog.catalog import display_principles, load_catalog
from principle_catalog.research import load_research_queries
from principle_catalog.site import _taxonomy_nav, _taxonomy_sections, build_site


def _built_html(tmp_path: Path) -> str:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    return (output / "index.html").read_text(encoding="utf-8")


def _card_openings(html: str) -> list[str]:
    return re.findall(r'<article class="principle-card"[^>]+>', html)


def test_pages_default_to_all_cards_and_expose_single_and_cumulative_coverage_filters(
    tmp_path: Path,
) -> None:
    html = _built_html(tmp_path)
    catalog = load_catalog()
    cards = _card_openings(html)

    assert '<select id="coverage-filter">' in html
    assert '<span>導入層</span>' in html
    all_option = '<option value="all">全て</option>'
    options = (
        '<option value="all">全て</option>',
        '<option value="core-only">骨格のみ</option>',
        '<option value="standard-only">標準のみ</option>',
        '<option value="advanced-only">発展のみ</option>',
        '<option value="core+standard">骨格＋標準</option>',
    )
    assert all(option in html for option in options)
    assert [html.index(option) for option in options] == sorted(
        html.index(option) for option in options
    )

    tiers = Counter(
        re.search(r'data-coverage-tier="([123])"', card).group(1)  # type: ignore[union-attr]
        for card in cards
    )
    expected_counts = catalog.coverage.schemes[catalog.coverage.current].constraints.tier_counts
    assert len(cards) == len(display_principles(catalog, published_only=True))
    assert tiers == {str(tier): count for tier, count in expected_counts.items()}
    assert sum(count for tier, count in tiers.items() if int(tier) <= 1) == expected_counts[1]
    assert sum(count for tier, count in tiers.items() if int(tier) <= 2) == expected_counts[1] + expected_counts[2]
    assert sum(tiers.values()) == len(cards)

    expected_labels = {"1": "骨格", "2": "標準", "3": "発展"}
    expected_slugs = {"1": "foundation", "2": "standard", "3": "advanced"}
    for card in cards:
        tier = re.search(r'data-coverage-tier="([123])"', card).group(1)  # type: ignore[union-attr]
        label = unescape(
            re.search(r'data-coverage-label="([^"]+)"', card).group(1)  # type: ignore[union-attr]
        )
        search_text = unescape(
            re.search(r'data-search="([^"]*)"', card).group(1)  # type: ignore[union-attr]
        )
        assert label == expected_labels[tier]
        assert label.casefold() in search_text
    for tier, count in tiers.items():
        badge = (
            f'<span class="coverage-badge coverage-{expected_slugs[tier]}">'
            f"{expected_labels[tier]}</span>"
        )
        assert html.count(badge) == count

    scheme = re.search(r'data-coverage-scheme="([^"]+)"', html)
    assert scheme is not None
    assert f"導入層版：{scheme.group(1)}" in html
    assert f'<div><strong>{len(cards)}</strong><span>公開項目</span></div>' in html
    assert html.count(f"{catalog.question_editions.current} Q") >= len(cards)


def test_zero_public_fire_group_shows_only_aggregate_pending_coverage(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    queries = load_research_queries(catalog)
    fire_subtopics = {
        subtopic.id
        for group in catalog.taxonomy.groups
        if group.id == "steel.fire-special"
        for subtopic in group.subtopics
    }
    catalog = replace(catalog, principles=tuple(
        replace(item, editorial_status="source_gap", question=None)
        if catalog.taxonomy.assignments[item.id] in fire_subtopics else item
        for item in catalog.principles
    ))
    published = display_principles(catalog, published_only=True)
    anchors = {item.id: () for item in published}
    html = _taxonomy_nav(catalog, published) + _taxonomy_sections(
        catalog, published, {}, catalog.question_editions.editions[catalog.question_editions.current], anchors, anchors, queries,
    )
    private_fire_items = [
        item
        for item in catalog.principles
        if catalog.taxonomy.assignments[item.id] in fire_subtopics
        and item.editorial_status != "source_checked"
    ]

    assert private_fire_items
    assert (
        f'<p class="coverage-gap-notice">耐火・特殊荷重：根拠確認待ち{len(private_fire_items)}件</p>'
        in html
    )
    assert 'href="#group-steel.fire-special"' not in html
    assert 'id="group-steel.fire-special"' not in html
    for subtopic_id in fire_subtopics:
        assert f'id="subtopic-{subtopic_id}"' not in html
    for item in private_fire_items:
        assert item.id not in html
        assert item.code not in html
        assert item.principle not in html
