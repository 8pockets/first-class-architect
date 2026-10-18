"""Progressive study entry points preserve the existing catalog contracts."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from principle_catalog.catalog import coverage_introduction_order, display_principles, load_catalog
from principle_catalog.research import load_research_queries
from principle_catalog.site import _page, build_site


BASE_URL = "https://8pockets.github.io/first-class-architect/"


class Markup(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.elements = []
        self.stack = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "parents": tuple(self.stack)}
        self.elements.append(node)
        if tag not in {"input", "meta", "link", "br", "img", "hr", "path"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def by_id(self, identifier):
        return next(node for node in self.elements if node["attrs"].get("id") == identifier)


@pytest.fixture(scope="module")
def page():
    catalog = load_catalog()
    html = _page(BASE_URL, catalog, load_research_queries(catalog))
    return catalog, html, Markup(html)


def test_entry_is_progressively_enhanced_and_keeps_existing_cards(page):
    catalog, html, markup = page
    dashboard = markup.by_id("study-dashboard")
    assert "hidden" in dashboard["attrs"]
    assert any(node["tag"] == "main" for node in dashboard["parents"])
    assert html.index('id="study-dashboard"') < html.index('id="catalog-controls"')
    assert html.index('id="study-session"') < html.index('id="catalog"')
    for identifier in ("study-start", "study-resume", "study-review", "study-browse", "study-toggle-answers", "study-finish", "study-pause", "study-return"):
        assert markup.by_id(identifier)["attrs"]["type"] == "button"
    for identifier in ("study-resume", "study-session", "study-return", "study-card-list"):
        assert "hidden" in markup.by_id(identifier)["attrs"]
    assert 'id="study-prev"' not in html
    assert 'id="study-next"' not in html
    assert markup.by_id("study-status")["attrs"]["role"] == "status"
    assert markup.by_id("study-session-progress")["attrs"]["aria-live"] == "polite"
    assert markup.by_id("study-map")["tag"] == "details"
    assert len([node for node in markup.elements if node["attrs"].get("class") == "principle-card"]) == len(display_principles(catalog, published_only=True))
    assert "回答の採点・保存・絞込みにはJavaScriptが必要です" in html


def test_study_set_has_one_list_and_its_own_bulk_answer_control(page):
    _, _, markup = page
    card_list = markup.by_id("study-card-list")
    assert card_list["attrs"]["class"] == "study-card-list"
    assert card_list["parents"][-1]["attrs"].get("id") == "catalog"
    assert not any(card_list in node["parents"] for node in markup.elements)
    toggle = markup.by_id("study-toggle-answers")
    assert "data-toggle-visible-answers" in toggle["attrs"]
    assert toggle["attrs"]["aria-controls"] == "catalog"
    assert toggle["attrs"]["aria-pressed"] == "false"
    assert any(parent["attrs"].get("id") == "study-session" for parent in toggle["parents"])
    assert "data-toggle-visible-answers" in markup.by_id("toggle-visible-answers")["attrs"]


def test_cards_expose_stable_schedule_and_taxonomy_metadata(page):
    catalog, _, markup = page
    expected_order = {item.id: index + 1 for index, item in enumerate(coverage_introduction_order(catalog))}
    items = {item.id: item for item in catalog.principles}
    cards = [node["attrs"] for node in markup.elements if node["attrs"].get("class") == "principle-card"]
    for card in cards:
        item = items[card["data-study-id"]]
        assert int(card["data-introduction-order"]) == expected_order[item.id]
        assert card["data-section"] == catalog.taxonomy.assignments[item.id]
        assert card["data-section-title"]
        assert card["data-group"]
        assert card["data-group-title"]
        assert card["data-prerequisites"].split() == list(item.prerequisites)


def test_prerequisite_links_stay_inside_answer_and_have_public_targets(page):
    catalog, _, markup = page
    targets = {item.id: item.code for item in display_principles(catalog, published_only=True)}
    links = [node for node in markup.elements if "data-prerequisite-link" in node["attrs"]]
    assert links
    for link in links:
        assert link["attrs"]["href"] == "#" + targets[link["attrs"]["data-prerequisite-link"]]
        assert any("data-answer-disclosure" in parent["attrs"] for parent in link["parents"])


def test_search_and_progress_fold_without_hiding_save_status(page):
    _, _, markup = page
    for identifier in ("progress-filter", "source-kind-filter"):
        assert any(parent["attrs"].get("class") == "advanced-filters" for parent in markup.by_id(identifier)["parents"])
    for identifier in ("catalog-search", "review-filter", "coverage-filter"):
        assert any(parent["attrs"].get("id") == "catalog-browser" for parent in markup.by_id(identifier)["parents"])
    for identifier in ("history-status", "study-status"):
        assert not any(parent["tag"] == "details" for parent in markup.by_id(identifier)["parents"])
        assert markup.by_id(identifier)["parents"][-1]["attrs"].get("class") == "study-notices"
    assert any(parent["attrs"].get("class") == "study-progress-summary" for parent in markup.by_id("study-metrics")["parents"])
    for identifier in ("history-export", "history-import"):
        assert any(parent["tag"] == "details" for parent in markup.by_id(identifier)["parents"])


def test_count_targets_and_scripts_have_explicit_contracts(page):
    _, html, markup = page
    counts = [node for node in markup.elements if "data-count-for" in node["attrs"]]
    assert len(counts) == 9 + 9 + 47
    for node in counts:
        assert int(node["attrs"]["data-total-count"]) > 0
        assert markup.by_id(node["attrs"]["data-count-for"])
    scripts = ["answer-history.js", "study-session.js", "catalog.js", "study-ui.js", "practice-ui.js"]
    assert [html.index(f"assets/{name}") for name in scripts] == sorted(html.index(f"assets/{name}") for name in scripts)
    for name in scripts:
        assert re.search(rf'<script defer src="[^"]*/assets/{re.escape(name)}"></script>', html)


def test_zoom_is_allowed_and_new_ui_is_hidden_when_printed(page):
    _, html, _ = page
    assert 'content="width=device-width, initial-scale=1"' in html
    assert "user-scalable=no" not in html
    assert "maximum-scale=1" not in html
    css = Path("principle_catalog/static/styles.css").read_text(encoding="utf-8")
    assert "touch-action: manipulation" in css
    print_css = css.split("@media print", 1)[1]
    for selector in (".study-dashboard", ".study-session", ".study-return", ".practice-panel", ".prerequisite-links"):
        rule = re.search(rf"{re.escape(selector)}(?:\s*,[^{{]*)?\s*\{{([^}}]*)\}}", print_css)
        assert rule is not None and "display: none !important" in rule.group(1)
    list_rule = re.search(r"\.study-card-list\s*\{([^}]*)\}", print_css)
    assert list_rule is not None and "display: contents" in list_rule.group(1)
    assert "study-card-next" not in css


def test_card_tools_fold_without_hiding_question_or_answer(page):
    _, _, markup = page
    tools = [node for node in markup.elements if node["attrs"].get("class") == "card-tools"]
    assert len(tools) == 311
    assert all("open" not in node["attrs"] for node in tools)
    for node in markup.elements:
        attrs = node["attrs"]
        classes = attrs.get("class", "").split()
        if "data-answer-history" in attrs or attrs.get("class") == "card-source" or "type-badge" in classes:
            assert any(parent["attrs"].get("class") == "card-tools" for parent in node["parents"])
        if "coverage-badge" in classes:
            assert any(parent["attrs"].get("class") == "card-header" for parent in node["parents"])
        if attrs.get("data-research-search") == "explanation":
            answer = next(parent for parent in node["parents"] if "data-answer-disclosure" in parent["attrs"])
            assert "open" not in answer["attrs"]
            assert not any(parent["attrs"].get("class") == "card-tools" for parent in node["parents"])
        if "data-answer-disclosure" in attrs or "data-answer-choice" in attrs:
            assert not any(parent["attrs"].get("class") == "card-tools" for parent in node["parents"])


def test_study_set_is_one_column_with_readable_gaps():
    css = Path("principle_catalog/static/styles.css").read_text(encoding="utf-8")
    list_rule = re.search(r"\.study-card-list\s*\{([^}]*)\}", css)
    assert list_rule is not None
    for declaration in ("grid-template-columns: minmax(0, 1fr)", "gap: 24px", "max-width: 780px"):
        assert declaration in list_rule.group(1)
    assert ".study-set-position" in css
    assert ".study-set-supplement .study-set-position" in css


def test_favorites_are_question_controls_separate_from_answers(page):
    _, _, markup = page
    buttons = [node for node in markup.elements if "data-favorite-toggle" in node["attrs"]]
    assert len(buttons) == 311
    for button in buttons:
        assert button["attrs"]["type"] == "button"
        assert button["attrs"]["aria-pressed"] == "false"
        assert "hidden" in button["attrs"]
        assert "お気に入り：K6-R3 Q" in button["attrs"]["aria-label"]
        assert any(parent["attrs"].get("class") == "card-header" for parent in button["parents"])
        assert not any("data-answer-disclosure" in parent["attrs"] for parent in button["parents"])
    assert markup.by_id("favorite-filter")["attrs"]["type"] == "checkbox"
    assert markup.by_id("favorite-status")["attrs"]["role"] == "status"


def test_stylesheet_cache_version_tracks_its_contents(page, monkeypatch):
    import hashlib
    from principle_catalog import site

    _, html, _ = page
    css = Path("principle_catalog/static/styles.css").read_bytes()
    expected = BASE_URL + "assets/styles.css?v=" + hashlib.sha256(css).hexdigest()[:12]
    assert f'href="{expected}"' in html
    assert site._stylesheet_url(BASE_URL) == expected
    monkeypatch.setattr(site, "_asset_text", lambda name: "changed stylesheet")
    assert site._stylesheet_url(BASE_URL) != expected


def test_new_script_assets_are_copied_to_static_release(tmp_path):
    output = tmp_path / "site"
    build_site(output, BASE_URL)
    for name in ("study-session.js", "study-ui.js", "practice-ui.js"):
        assert (output / "assets" / name).read_text(encoding="utf-8") == (Path("principle_catalog/static") / name).read_text(encoding="utf-8")
