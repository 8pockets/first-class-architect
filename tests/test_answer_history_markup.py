"""Public markup contracts for private, revision-aware answer history."""
from __future__ import annotations

import re
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml

from principle_catalog.catalog import (
    CatalogError, _load_section, display_facets, display_principles, load_catalog,
)
from principle_catalog.models import AuthoritativeSource, DisplayFacet
from principle_catalog.research import ResearchQueryPair
from principle_catalog.site import _card, build_site

BASE_URL = "https://8pockets.github.io/first-class-architect/"


def _render(catalog, item, *, facets=None, number=1, reference="K6-R99 Q001"):
    return _card(
        catalog, item, "unstarted", number, reference, (), (),
        facets or display_facets(catalog, item), ("鉄骨構造", "中立の分類名"),
        ResearchQueryPair("鉄骨構造 一次資料", "鉄骨構造 解説"),
    )


def _revision(html):
    return re.search(r'data-question-revision="([0-9a-f]{64})"', html).group(1)


class _InitialAccessibleText(HTMLParser):
    """Read initial text/accessible labels, excluding closed details content."""

    def __init__(self):
        super().__init__()
        self.stack = []
        self.values = []

    def visible(self):
        if any(hidden for _, hidden in self.stack):
            return False
        details = [i for i, (tag, _) in enumerate(self.stack) if tag == "details"]
        return not details or any(tag == "summary" for tag, _ in self.stack[details[-1] + 1:])

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag not in {"br", "input", "meta", "link", "img", "hr"}:
            self.stack.append((tag, "hidden" in attributes))
        if self.visible():
            self.values.extend(attributes[key] for key in ("aria-label", "title") if key in attributes)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.visible():
            self.values.append(data)


def test_question_revision_tracks_question_and_taught_content_not_number_or_order():
    catalog = load_catalog()
    item = display_principles(catalog, published_only=True)[0]
    baseline = _revision(_render(catalog, item))
    assert baseline == _revision(_render(catalog, replace(item, order=item.order + 1), number=999, reference="K6-R100 Q999"))
    for question in (
        replace(item.question, prompt=item.question.prompt + "条件変更"),
        replace(item.question, choice_a=item.question.choice_a + "変更"),
        replace(item.question, choice_b=item.question.choice_b + "変更"),
        replace(item.question, correct="B" if item.question.correct == "A" else "A"),
        replace(item.question, figure="hysteresis-loops-v1" if item.question.figure is None else None),
    ):
        assert baseline != _revision(_render(catalog, replace(item, question=question)))
    facets = display_facets(catalog, item)
    for field in ("primary", "secondary", "tertiary"):
        facet = getattr(facets, field)
        changed = replace(facets, **{field: replace(facet, values=(*facet.values, "内容変更"))})
        assert baseline != _revision(_render(catalog, item, facets=changed))
    assert baseline == _revision(_render(catalog, replace(item, source=replace(item.source, question_codes=()))))


def test_answer_title_and_semantic_code_do_not_leak_via_initial_text_or_accessible_labels():
    catalog = load_catalog()
    item = replace(display_principles(catalog, published_only=True)[0],
                   principle="ANSWER_TITLE_SENTINEL", code="structure.steel.answer-name-sentinel")
    item = replace(item, source=replace(item.source, authoritative_sources=(
        AuthoritativeSource("law", "ANSWER_SOURCE_TITLE_SENTINEL", "ANSWER_SOURCE_LOCATION_SENTINEL",
                            "https://example.go.jp/answer-source", ("statement",)),
    )))
    facets = replace(display_facets(catalog, item), primary=DisplayFacet("結論", ("ANSWER_CONTENT_SENTINEL",)))
    html = _render(catalog, item, facets=facets)
    reader = _InitialAccessibleText()
    reader.feed(html)
    initially_accessible = " ".join(reader.values)
    assert "中立の分類名" in initially_accessible
    assert "K6-R99 Q001" in initially_accessible
    assert "ANSWER_TITLE_SENTINEL" not in initially_accessible
    assert "ANSWER_CONTENT_SENTINEL" not in initially_accessible
    assert "ANSWER_SOURCE_TITLE_SENTINEL" not in initially_accessible
    assert "ANSWER_SOURCE_LOCATION_SENTINEL" not in initially_accessible
    assert item.code not in initially_accessible
    assert item.id not in initially_accessible
    assert "ANSWER_TITLE_SENTINEL" in html
    assert "ANSWER_CONTENT_SENTINEL" in html
    answer = html.split('<div class="answer-content">', 1)[1].split("</details>", 1)[0]
    assert "ANSWER_SOURCE_TITLE_SENTINEL" in answer
    assert "ANSWER_SOURCE_LOCATION_SENTINEL" in answer
    assert 'data-answer-choice="A"' in html and 'data-answer-choice="B"' in html


def test_history_assets_and_browser_only_controls_are_present_without_outbound_requests(tmp_path: Path):
    build_site(tmp_path / "site", BASE_URL)
    output = tmp_path / "site"
    html = (output / "index.html").read_text(encoding="utf-8")
    history = (output / "assets/answer-history.js").read_text(encoding="utf-8")
    script = (output / "assets/catalog.js").read_text(encoding="utf-8")
    assert html.index('assets/answer-history.js') < html.index('assets/catalog.js')
    for asset in ("answer-history.js", "catalog.js"):
        tag = re.search(rf'<script[^>]+src="[^"]*/assets/{re.escape(asset)}(?:\?v=[a-f0-9]{{12}})?"[^>]*>', html)
        assert tag is not None and "defer" in tag.group(0)
    assert history == Path("principle_catalog/static/answer-history.js").read_text(encoding="utf-8")
    assert "localStorage" in script
    for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "document.cookie", "https://", "http://"):
        assert forbidden not in history + script
    assert "端末間の自動同期はありません" in html
    assert 'id="history-export"' in html
    assert 'id="history-import" type="file"' in html
    assert 'id="history-status" role="status"' in html
    for value in ("all", "unanswered", "review", "priority", "history"):
        select = html.split('<select id="review-filter">', 1)[1].split("</select>", 1)[0]
        assert f'value="{value}"' in select
    published_count = len(display_principles(load_catalog(), published_only=True))
    for marker in ('data-study-id="', 'data-question-revision="', "data-answer-result", "data-answer-status-details", "data-answer-retry", "data-answer-history-list"):
        assert html.count(marker) == published_count


def test_print_sheet_hides_history_result_retry_and_answers_without_choice_scoring_colors(tmp_path: Path):
    build_site(tmp_path / "site", BASE_URL)
    css = (tmp_path / "site/assets/styles.css").read_text(encoding="utf-8")
    print_css = css.split("@media print", 1)[1]
    for selector in (".answer-feedback", ".answer-history", ".answer-retry", ".study-history-controls", ".answer-disclosure"):
        rule = re.search(rf"{re.escape(selector)}(?:\s*,[^{{]*)?\s*\{{([^}}]*)\}}", print_css)
        assert rule is not None, selector
        assert "display: none !important" in rule.group(1), selector
    assert "data-correct-choice" not in css
    assert "data-answer-choice=\"A\"" not in css
    assert "data-answer-choice=\"B\"" not in css
    selected_print = re.search(r'\.choice-button\[aria-pressed="true"\]\s*\{([^}]*)\}', print_css)
    assert selected_print is not None
    assert "background: transparent" in selected_print.group(1)
    assert "border: 0" in selected_print.group(1)
    assert "color: #000" in selected_print.group(1)
    feedback_css = re.search(r'@media screen\s*\{([^}]*data-answer-feedback[^}]*\}[^}]*\})\s*\}', css)
    assert feedback_css is not None
    assert 'data-answer-feedback="correct"' in feedback_css.group(1)
    assert 'data-answer-feedback="incorrect"' in feedback_css.group(1)
    assert "data-answer-feedback" not in print_css


def _typed_fixture(tmp_path, item_type):
    catalog = load_catalog()
    for path in catalog.manifest.section_files:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        candidate = next((item for item in document["principles"]
                          if item["type"] == item_type and item["editorial_status"] == "source_checked"), None)
        if candidate:
            document["principles"] = [candidate]
            candidate["reason"] = "教材に記載なし"
            candidate["verification"] = {"statement_source": "verified", "explanation_completeness": "complete", "conditions_completeness": "complete"}
            fixture = tmp_path / f"{item_type}.yaml"
            return catalog, document, candidate, fixture
    raise AssertionError(f"missing {item_type} fixture")


@pytest.mark.parametrize("item_type", ["rule", "identification"])
def test_typed_legacy_reason_gap_is_allowed_only_with_explicit_verified_display(tmp_path: Path, item_type):
    catalog, document, item, fixture = _typed_fixture(tmp_path, item_type)
    def load():
        fixture.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return _load_section(fixture, catalog.manifest)
    assert load()[0].reason == "教材に記載なし"
    verification = item.pop("verification")
    with pytest.raises(CatalogError, match="explicit typed verification"):
        load()
    item["verification"] = verification
    field = "applicability" if item_type == "rule" else "distinguishing_conditions"
    item["display_content"][field] = ["教材に記載なし"]
    with pytest.raises(CatalogError, match="cannot have missing evidence"):
        load()
    item["display_content"][field] = []
    with pytest.raises(CatalogError, match="must not be empty"):
        load()


def test_principle_reason_gap_remains_rejected(tmp_path: Path):
    catalog, document, item, fixture = _typed_fixture(tmp_path, "principle")
    fixture.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(CatalogError, match="source gap"):
        _load_section(fixture, catalog.manifest)
