"""Public Pages coverage-layer contracts."""

from __future__ import annotations

import re
from collections import Counter
from html import unescape
from pathlib import Path

from principle_catalog.catalog import load_catalog
from principle_catalog.site import build_site


def _built_html(tmp_path: Path) -> str:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    return (output / "index.html").read_text(encoding="utf-8")


def _card_openings(html: str) -> list[str]:
    return re.findall(r'<article class="principle-card"[^>]+>', html)


def test_pages_default_to_all_cards_and_expose_cumulative_coverage_filters(
    tmp_path: Path,
) -> None:
    html = _built_html(tmp_path)
    cards = _card_openings(html)

    assert '<select id="coverage-filter">' in html
    assert '<span>導入層</span>' in html
    all_option = '<option value="all">全て</option>'
    core_option = '<option value="1">骨格のみ</option>'
    standard_option = '<option value="2">標準まで</option>'
    assert all_option in html
    assert core_option in html
    assert standard_option in html
    assert html.index(all_option) < html.index(core_option) < html.index(standard_option)
    assert '<option value="3">' not in html

    tiers = Counter(
        re.search(r'data-coverage-tier="([123])"', card).group(1)  # type: ignore[union-attr]
        for card in cards
    )
    assert len(cards) == 116
    assert tiers == {"1": 32, "2": 42, "3": 42}
    assert sum(count for tier, count in tiers.items() if int(tier) <= 1) == 32
    assert sum(count for tier, count in tiers.items() if int(tier) <= 2) == 74
    assert sum(tiers.values()) == 116

    expected_labels = {"1": "骨格", "2": "標準", "3": "発展"}
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

    scheme = re.search(r'data-coverage-scheme="([^"]+)"', html)
    assert scheme is not None
    assert f"導入層版：{scheme.group(1)}" in html
    assert '<div><strong>116</strong><span>公開項目</span></div>' in html
    assert html.count("K6-R2 Q") >= 116


def test_zero_public_fire_group_shows_only_aggregate_pending_coverage(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    html = _built_html(tmp_path)
    fire_subtopics = {
        subtopic.id
        for group in catalog.taxonomy.groups
        if group.id == "steel.fire-special"
        for subtopic in group.subtopics
    }
    private_fire_items = [
        item
        for item in catalog.principles
        if catalog.taxonomy.assignments[item.id] in fire_subtopics
        and item.editorial_status != "source_checked"
    ]

    assert len(private_fire_items) == 8
    assert (
        '<p class="coverage-gap-notice">耐火・特殊荷重：根拠確認待ち8件</p>'
        in html
    )
    for item in private_fire_items:
        assert item.id not in html
        assert item.code not in html
        assert item.principle not in html
