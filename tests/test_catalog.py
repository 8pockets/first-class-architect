from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter
from dataclasses import replace
from html import escape
from pathlib import Path

import pytest
import yaml

from principle_catalog.catalog import (
    CATALOG_ROOT,
    CatalogError,
    MANIFEST_PATH,
    PUBLIC_PROGRESS_PATH,
    _has_repeating_answer_period,
    display_facets,
    display_principles,
    load_catalog,
    load_public_progress,
    validate_print_registry_history,
)
from principle_catalog.models import PublicProgressProjection
from principle_catalog.progress import _coarse_status, public_progress_from_local
from principle_catalog.site import build_site
from principle_catalog.study import study_brief, sync_study_items


EXPECTED_SHA256 = "33b77550756a6994fe07ab653aaf4ab046c08765c980a62f7f555eea2cda0ec8"
LOCAL_STUDY_STATE = Path(".study/state.json")


def _copy_catalog(tmp_path: Path) -> Path:
    root = tmp_path / "steel"
    shutil.copytree(CATALOG_ROOT, root)
    return root


def _rewrite_item(
    section: Path,
    *,
    source_checked: bool,
    question: object = ...,
) -> None:
    document = yaml.safe_load(section.read_text(encoding="utf-8"))
    item = next((candidate for candidate in document["principles"]
                 if (candidate["editorial_status"] == "source_checked") is source_checked),
                document["principles"][0])
    item["editorial_status"] = "source_checked" if source_checked else "source_gap"
    if question is ...:
        item.pop("question", None)
    else:
        item["question"] = question
    section.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _css_declarations(css: str, selector: str) -> dict[str, str]:
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert match is not None, f"missing CSS rule: {selector}"
    declarations: dict[str, str] = {}
    for raw in match.group(1).split(";"):
        if ":" not in raw:
            continue
        name, value = raw.split(":", maxsplit=1)
        declarations[name.strip()] = value.strip()
    return declarations


def _print_registry_digest(assignments: dict[str, int]) -> str:
    audited = [
        {"id": item_id, "number": number}
        for item_id, number in sorted(
            assignments.items(),
            key=lambda assignment: assignment[1],
        )
    ]
    canonical = json.dumps(
        audited,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_manifest_covers_every_requested_pdf_page() -> None:
    catalog = load_catalog()

    assert catalog.manifest.source_sha256 == EXPECTED_SHA256
    assert catalog.manifest.first_page == 158
    assert catalog.manifest.last_page == 215
    assert catalog.manifest.audited_pages == tuple(range(158, 216))
    assert catalog.audit.table_pages == tuple(range(159, 176))
    assert catalog.audit.table_row_count == 167
    assert len(catalog.audit.primary_question_codes) == 167
    assert catalog.manifest.expected_total == len(catalog.principles)
    statuses = Counter(item.editorial_status for item in catalog.principles)
    assert catalog.manifest.expected_status_counts == {
        status: statuses[status] for status in ("draft", "source_checked", "source_gap")
    }
    assert catalog.manifest.expected_answer_counts == Counter(
        item.question.correct for item in display_principles(catalog, published_only=True)
    )


def test_manifest_preserves_the_archived_r1_print_registry() -> None:
    catalog = load_catalog()
    archived = catalog.question_editions.editions["K6-R1"]

    assert catalog.manifest.next_print_number == 117
    assert len(catalog.manifest.print_numbers) == 116
    assert archived.status == "archived"
    assert archived.assignments == catalog.manifest.print_numbers
    assert set(catalog.manifest.print_numbers.values()) == set(range(1, 117))
    assert catalog.manifest.print_registry_sha256 == (
        "7b2a0e8e18bccb17560dc97e56a9fdcd70d242e8f18db0aa58ba1357969894ec"
    )


def test_print_number_swap_without_registry_reaudit_is_rejected(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    manifest_path = root / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assignments = manifest["print_registry"]["assignments"]
    first, second = list(assignments)[:2]
    assignments[first], assignments[second] = assignments[second], assignments[first]
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="permanent print registry snapshot"):
        load_catalog(manifest_path)


def test_print_number_swap_is_rejected_even_after_snapshot_is_recomputed(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    previous_manifest = tmp_path / "previous-manifest.yaml"
    manifest_path = root / "manifest.yaml"
    previous_manifest.write_text(
        manifest_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assignments = manifest["print_registry"]["assignments"]
    first, second = list(assignments)[:2]
    assignments[first], assignments[second] = assignments[second], assignments[first]
    manifest["print_registry"]["content_sha256"] = _print_registry_digest(
        assignments
    )
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="existing print numbers must not change"):
        validate_print_registry_history(previous_manifest, manifest_path)


def test_new_print_number_cannot_be_reserved_for_an_unpublished_item(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    previous_manifest = tmp_path / "previous-manifest.yaml"
    manifest_path = root / "manifest.yaml"
    previous_manifest.write_text(
        manifest_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    catalog = load_catalog(manifest_path)
    unpublished = next(
        item
        for item in catalog.principles
        if item.id not in catalog.manifest.print_numbers
    )
    section_path = next(path for path in catalog.manifest.section_files
                        if any(item["id"] == unpublished.id for item in yaml.safe_load(path.read_text())["principles"]))
    section_document = yaml.safe_load(section_path.read_text(encoding="utf-8"))
    candidate = next(item for item in section_document["principles"] if item["id"] == unpublished.id)
    candidate["editorial_status"] = "source_gap"
    candidate.pop("question", None)
    section_path.write_text(yaml.safe_dump(section_document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    registry = manifest["print_registry"]
    registry["assignments"][unpublished.id] = registry["next_number"]
    registry["next_number"] += 1
    registry["content_sha256"] = _print_registry_digest(registry["assignments"])
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="only be assigned to source-checked"):
        validate_print_registry_history(previous_manifest, manifest_path)


def test_every_audited_content_page_and_table_row_is_cataloged() -> None:
    catalog = load_catalog()
    covered_pages = {page for item in catalog.principles for page in item.source.pages}
    content_pages = set(catalog.manifest.audited_pages) - set(
        catalog.audit.page_kinds["chapter_cover"]
    )
    question_codes = {
        code for item in catalog.principles for code in item.source.question_codes
    }

    assert content_pages <= covered_pages
    assert set(catalog.audit.primary_question_codes) <= question_codes


def test_catalog_has_unique_ordered_ids_and_valid_prerequisites() -> None:
    catalog = load_catalog()
    ids = [item.id for item in catalog.principles]

    assert len(ids) == len(set(ids))
    assert ids == [
        item.id
        for item in sorted(
            catalog.principles,
            key=lambda item: (item.section_order, item.order, item.id),
        )
    ]
    assert all(set(item.prerequisites) <= set(ids) for item in catalog.principles)


@pytest.mark.skipif(
    not LOCAL_STUDY_STATE.exists(),
    reason="private local study state is intentionally absent in CI",
)
def test_existing_study_items_are_stable_catalog_ids() -> None:
    catalog = load_catalog()
    catalog_ids = {item.id for item in catalog.principles} | set(
        catalog.migration.retired
    )
    state = json.loads(LOCAL_STUDY_STATE.read_text(encoding="utf-8"))
    study_ids = {
        item["id"] for item in state["items"] if item["id"].startswith("S-K6-")
    }

    assert study_ids <= catalog_ids


def test_source_checked_entries_have_balanced_binary_questions_and_three_point_content() -> None:
    catalog = load_catalog()
    checked = list(display_principles(catalog, published_only=True))

    assert len(checked) == catalog.manifest.expected_status_counts["source_checked"]
    for item in checked:
        assert item.principle
        assert item.question
        assert item.question.prompt.endswith("正しい結論はどちらか。")
        assert "説明しなさい" not in item.question.prompt
        assert "述べなさい" not in item.question.prompt
        assert item.question.choice_a
        assert item.question.choice_b
        assert item.question.choice_a != item.question.choice_b
        assert item.question.correct in {"A", "B"}
        assert max(len(item.question.choice_a), len(item.question.choice_b)) <= 40
        assert abs(len(item.question.choice_a) - len(item.question.choice_b)) <= 10
        assert not any(
            clue in f"{item.question.choice_a} {item.question.choice_b}"
            for clue in (
                "必ず",
                "絶対",
                "両方",
                "双方",
                "いずれも",
                "どちらも",
                "どちらでもない",
            )
        )
        assert item.conclusion
        if item.type == "principle":
            assert item.reason != "教材に記載なし"
        else:
            assert display_facets(catalog, item).typed
        assert item.conditions
        assert "教材に記載なし" not in item.conditions

    normalized_questions = {
        unicodedata.normalize("NFKC", item.question.prompt).casefold().strip()
        for item in checked
        if item.question is not None
    }
    assert len(normalized_questions) == len(checked)
    answer_key = [item.question.correct for item in checked if item.question]
    assert Counter(answer_key) == catalog.manifest.expected_answer_counts
    # Each introduction tier is balanced; odd-sized tiers may sum to a small
    # overall difference while retaining their independently audited targets.
    assert abs(answer_key.count("A") - answer_key.count("B")) <= len(catalog.coverage.tiers)
    runs: list[list[str]] = []
    for label in answer_key:
        if not runs or runs[-1][-1] != label:
            runs.append([label])
        else:
            runs[-1].append(label)
    assert max(map(len, runs)) <= 3
    assert len(runs) >= len(checked) // 2
    assert not _has_repeating_answer_period(tuple(answer_key))


@pytest.mark.parametrize(
    "answer_key",
    [
        tuple("AB" * 58),
        tuple("AABB" * 29),
        tuple(("ABBA" * 14 + "AB") * 2),
    ],
)
def test_repeating_answer_position_patterns_are_rejected(
    answer_key: tuple[str, ...],
) -> None:
    assert _has_repeating_answer_period(answer_key)


def test_public_progress_is_exact_coarse_projection_of_local_state() -> None:
    actual = load_public_progress().items
    catalog_ids = {item.id for item in load_catalog().principles}

    if LOCAL_STUDY_STATE.exists():
        assert actual == public_progress_from_local()
    assert set(actual) <= catalog_ids
    assert set(actual.values()) <= {"learning", "reviewing", "retained_14d"}


def test_public_progress_file_contains_no_private_study_fields() -> None:
    text = PUBLIC_PROGRESS_PATH.read_text(encoding="utf-8")
    forbidden = {
        "last_passed_on",
        "next_due_on",
        "consecutive_failures",
        "observed_gap",
        "result_id",
        "recorded_at",
        "hint",
        "cause",
        "raw",
    }

    assert not any(field in text for field in forbidden)


def test_build_publishes_only_source_checked_entries(tmp_path: Path) -> None:
    output = tmp_path / "site"
    published, planned = build_site(
        output,
        "https://8pockets.github.io/first-class-architect/",
    )
    catalog = load_catalog()
    html = (output / "index.html").read_text(encoding="utf-8")

    expected_published = [
        item for item in catalog.principles if item.editorial_status == "source_checked"
    ]
    unpublished = [
        item for item in catalog.principles if item.editorial_status != "source_checked"
    ]
    assert published == len(expected_published)
    assert planned == len(catalog.principles)
    assert html.count('class="principle-card"') == published
    assert html.count("確認問題（自作・2択）") == published
    assert html.count('class="binary-choices"') == published
    assert html.count('class="choice-button"') == published * 2
    assert html.count("data-answer-choice") == published * 2
    assert html.count('class="answer-disclosure"') == published
    assert html.count('<details id="answer-') == published
    assert html.count("正解と解説を見る") == published
    assert html.count("正解と解説を閉じる") == published
    assert html.count('class="answer-key"') == published
    assert all(item.principle in html for item in expected_published)
    assert all(
        item.question
        and item.question.prompt in html
        and item.question.choice_a in html
        and item.question.choice_b in html
        for item in expected_published
    )
    assert all(f'id="{item.code}"' not in html for item in unpublished)


def test_build_embeds_each_current_edition_reference_in_its_question_card(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    catalog = load_catalog()
    html = (output / "index.html").read_text(encoding="utf-8")
    published = list(display_principles(catalog, published_only=True))
    current = catalog.question_editions.editions[catalog.question_editions.current]
    expected_labels = [current.reference(item.id) for item in published]
    assert re.findall(
        r'class="print-question-number" aria-hidden="true">'
        r'<span data-print-position>問\d+</span> \[(K6-R\d+ Q\d{3})\]</p>',
        html,
    ) == expected_labels

    for item in published:
        card = html.split(f'id="{item.code}"', maxsplit=1)[1].split(
            "</article>", maxsplit=1
        )[0]
        reference = current.reference(item.id)
        assert (
            f'<span data-print-position>問{current.assignments[item.id]}</span> '
            f'[{reference}]'
            in card
        )


def test_learning_pages_allow_zoom_for_readability(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    expected = (
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
    )
    pages = [output / "index.html", output / "404.html"]
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert html.count('name="viewport"') == 1
        assert expected in html

    css = (output / "assets/styles.css").read_text(encoding="utf-8")
    root = _css_declarations(css, ":root")
    assert root["touch-action"] == "manipulation"


def test_research_page_allows_zoom_for_readability(tmp_path: Path) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    html = (output / "research/index.html").read_text(encoding="utf-8")
    css = (output / "assets/styles.css").read_text(encoding="utf-8")

    assert '<html lang="ja" class="research-document">' in html
    assert (
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        in html
    )
    assert ":root.research-document" not in css
    root = _css_declarations(css, ":root")
    assert root["touch-action"] == "manipulation"


def test_build_places_each_question_before_its_three_point_answer_and_searches_it(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    html = (output / "index.html").read_text(encoding="utf-8")
    catalog = load_catalog()
    published = display_principles(catalog, published_only=True)

    for item in published:
        assert item.question is not None
        facets = display_facets(catalog, item)
        card = html.split(f'id="{item.code}"', maxsplit=1)[1].split(
            "</article>", maxsplit=1
        )[0]
        card_body = card.split(">", maxsplit=1)[1]
        prompt = escape(item.question.prompt)
        choice_a = escape(item.question.choice_a)
        choice_b = escape(item.question.choice_b)
        search_text = card.split('data-search="', maxsplit=1)[1].split('"', maxsplit=1)[0]
        question_opening = card.split('<div class="practice-question"', maxsplit=1)[
            1
        ].split(">", maxsplit=1)[0]

        subtopic = catalog.taxonomy.assignments[item.id]
        neutral_title = next(topic.title for group in catalog.taxonomy.groups for topic in group.subtopics if topic.id == subtopic)
        heading = f"<h3>{escape(neutral_title)}</h3>"
        assert card_body.index(heading) < card_body.index(
            '<div class="practice-question"'
        )
        assert card_body.index('<div class="practice-question"') < card_body.index(
            prompt
        )
        assert card_body.index(prompt) < card_body.index('<ul class="binary-choices">')
        answer_opening = (
            f'<details id="answer-{item.code}" class="answer-disclosure"'
        )
        assert card_body.index('<ul class="binary-choices">') < card_body.index(
            answer_opening
        )
        assert card_body.index(answer_opening) < card_body.index(
            '<p class="answer-key">'
        )
        answer = card_body.split(
            answer_opening, maxsplit=1
        )[1].split("</details>", maxsplit=1)[0]
        disclosure_opening = answer.split(">", maxsplit=1)[0]
        assert answer.index("正解と解説を見る") < answer.index(
            '<p class="answer-key">'
        )
        assert answer.index("正解と解説を閉じる") < answer.index(
            '<p class="answer-key">'
        )
        assert answer.count(
            f'<span class="visually-hidden">：{escape(catalog.question_editions.editions[catalog.question_editions.current].reference(item.id))}</span>'
        ) == 2
        assert answer.index('<p class="answer-key">') < answer.index(
            f"<dt>{escape(facets.primary.label)}</dt>"
        )
        assert answer.index(f"<dt>{escape(facets.primary.label)}</dt>") < answer.index(
            f"<dt>{escape(facets.secondary.label)}</dt>"
        )
        assert answer.index(f"<dt>{escape(facets.secondary.label)}</dt>") < answer.index(
            f"<dt>{escape(facets.tertiary.label)}</dt>"
        )
        assert "hidden" not in question_opening
        assert " open" not in disclosure_opening
        assert "name=" not in disclosure_opening
        assert "data-answer-disclosure" in disclosure_opening
        assert "<summary" in card
        assert "data-principle-link" in card
        assert f'<strong>{item.question.correct}</strong>' in card
        assert prompt in card
        assert choice_a in card
        assert choice_b in card
        assert escape(item.question.prompt.lower()) in search_text
        assert escape(item.question.choice_a.lower()) in search_text
        assert escape(item.question.choice_b.lower()) in search_text
        for facet in (facets.primary, facets.secondary, facets.tertiary):
            assert escape(facet.label.lower()) in search_text
            assert all(escape(value.lower()) in search_text for value in facet.values)


def test_confirmed_choices_are_buttons_that_control_their_answer(tmp_path: Path) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    html = (output / "index.html").read_text(encoding="utf-8")
    catalog = load_catalog()
    published = display_principles(catalog, published_only=True)

    assert html.count('class="choice-button"') == len(published) * 2
    assert html.count("data-answer-choice") == len(published) * 2
    assert html.count('<details id="answer-') == len(published)

    for item in published:
        card = html.split(f'id="{item.code}"', maxsplit=1)[1].split(
            "</article>", maxsplit=1
        )[0]
        answer_id = f"answer-{item.code}"
        assert card.count('class="choice-button"') == 2
        assert card.count('data-answer-choice') == 2
        # Optional variants live inside the answer; the canonical question
        # still has exactly A/B, an explicit retry, and a separate favorite control.
        question_controls = card.split('<details id="answer-', maxsplit=1)[0]
        assert question_controls.count('type="button"') == 4
        assert question_controls.count('data-favorite-toggle') == 1
        assert 'data-answer-choice="A"' in card
        assert 'data-answer-choice="B"' in card
        assert card.count(f'aria-controls="{answer_id}"') == 2
        assert card.count('aria-expanded="false"') == 2
        assert (
            f'<details id="{answer_id}" class="answer-disclosure" '
            "data-answer-disclosure>"
            in card
        )
        assert f'data-correct-choice="{item.question.correct}"' in card


def test_confirmed_choice_buttons_preserve_screen_and_print_design(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    css = (output / "assets/styles.css").read_text(encoding="utf-8")

    button = _css_declarations(css, ".choice-button")
    assert button["display"] == "grid"
    assert button["grid-template-columns"] == "2rem minmax(0, 1fr)"
    assert button["width"] == "100%"
    assert button["min-height"] == "44px"
    assert button["padding"] == "10px 12px"
    assert button["color"] == "var(--ink)"
    assert button["background"] == "#fffdf8"
    assert button["border-radius"] == "8px"
    assert button["font"] == "inherit"
    assert button["text-align"] == "left"
    assert button["cursor"] == "pointer"
    focus = _css_declarations(css, ".choice-button:focus-visible")
    assert focus["outline"] == "3px solid #ef9e6f"

    print_rules = css.split("@media print", maxsplit=1)[1]
    printed_button = _css_declarations(print_rules, ".choice-button")
    assert printed_button["display"] == "grid"
    assert printed_button["grid-template-columns"] == "2.2em minmax(0, 1fr)"
    assert printed_button["padding"] == "0"
    assert printed_button["color"] == "#000"
    assert printed_button["background"] == "transparent"
    assert printed_button["border"] == "0"
    printed_focus = _css_declarations(print_rules, ".choice-button:focus-visible")
    assert printed_focus["outline"] == "none"


def test_build_is_public_read_only_and_privacy_bounded(tmp_path: Path) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    html = (output / "index.html").read_text(encoding="utf-8")
    script = (output / "assets/catalog.js").read_text(encoding="utf-8")
    css = (output / "assets/styles.css").read_text(encoding="utf-8")

    assert "結論" in html
    assert "理由" in html
    assert "結論を左右する条件" in html
    assert "Cookie・外部解析なし" in html
    assert "/Users/" not in html
    assert ".study" not in html
    assert "2026_構造_文章問題.pdf" not in html
    assert "consecutive_failures" not in html
    assert "recorded_at" not in html
    assert "<form" not in html
    assert 'type="radio"' not in html
    assert re.search(r"\sdata-answer=", html) is None
    assert "fetch(" not in script
    assert "localStorage" in script  # Private browser history is now explicitly supported.
    assert "sessionStorage" not in script
    assert "document.cookie" not in script
    assert "http://" not in html + script + css
    assert "https://" not in script + css


def test_answer_disclosure_is_closed_by_default_and_accessible_on_screen(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    html = (output / "index.html").read_text(encoding="utf-8")
    css = (output / "assets/styles.css").read_text(encoding="utf-8")

    published_count = len(display_principles(load_catalog(), published_only=True))
    assert html.count('<details id="answer-') == published_count
    assert len(
        re.findall(
            r'<details id="answer-[^"]+" class="answer-disclosure" '
            r'data-answer-disclosure>\s*<summary>',
            html,
        )
    ) == published_count
    assert html.count('class="disclosure-label-closed"') == published_count
    assert html.count('class="disclosure-label-open"') == published_count
    assert (
        re.search(
            r'<details id="answer-[^"]+" class="answer-disclosure" '
            r'data-answer-disclosure open>',
            html,
        )
        is None
    )
    assert 'name="answer-disclosure"' not in html
    answer = _css_declarations(css, ".answer-disclosure")
    assert answer["background"] == "var(--card)"
    summary = _css_declarations(css, ".answer-disclosure > summary")
    assert summary["min-height"] == "52px"
    assert summary["cursor"] == "pointer"
    focus = _css_declarations(css, ".answer-disclosure > summary:focus-visible")
    assert focus["outline"] == "3px solid var(--orange)"
    assert focus["outline-offset"] == "-3px"
    labels = _css_declarations(
        css,
        ".answer-disclosure[open] .disclosure-label-closed,\n"
        ".answer-disclosure:not([open]) .disclosure-label-open",
    )
    assert labels["display"] == "none"
    visually_hidden = _css_declarations(css, ".visually-hidden")
    assert visually_hidden["position"] == "absolute"
    assert visually_hidden["clip"] == "rect(0 0 0 0)"
    mobile_rules = css.split("@media (max-width: 760px)", maxsplit=1)[1].split(
        "@media (prefers-reduced-motion: reduce)", maxsplit=1
    )[0]
    mobile_summary = _css_declarations(
        mobile_rules, ".answer-disclosure > summary"
    )
    assert mobile_summary["padding-right"] == "18px"
    assert mobile_summary["padding-left"] == "23px"


def test_controls_expose_one_accessible_visible_answer_bulk_toggle(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    html = (output / "index.html").read_text(encoding="utf-8")
    css = (output / "assets/styles.css").read_text(encoding="utf-8")

    opening = (
        '<button class="answer-toggle-button" id="toggle-visible-answers" '
        'type="button" data-toggle-visible-answers aria-controls="catalog" '
        'aria-pressed="false">'
    )
    assert html.count(opening) == 1
    assert f"{opening}表示中の答えをすべて開く</button>" in html
    button = _css_declarations(css, ".answer-toggle-button")
    assert button["min-height"] == "44px"
    assert button["cursor"] == "pointer"
    mobile_rules = css.split("@media (max-width: 760px)", maxsplit=1)[1].split(
        "@media (prefers-reduced-motion: reduce)", maxsplit=1
    )[0]
    mobile_button_rules = re.findall(
        r"\.answer-toggle-button\s*\{([^}]*)\}", mobile_rules
    )
    assert any("width: 100%" in rule for rule in mobile_button_rules)


def test_screen_typography_prioritizes_the_practice_question(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    css = (output / "assets/styles.css").read_text(encoding="utf-8")

    title = _css_declarations(css, ".card-header h3")
    question = _css_declarations(css, ".practice-question-text")

    assert title["font-size"] == "clamp(0.6rem, 1.4vw, 1rem)"
    assert question["font-size"] == "clamp(1.08rem, 1.7vw, 1.18rem)"


def test_print_styles_make_a_compact_a4_two_column_question_sheet(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    css = (output / "assets/styles.css").read_text(encoding="utf-8")
    print_rules = css.split("@media print", maxsplit=1)[1]

    page = _css_declarations(css, "@page")
    assert page == {"size": "A4 portrait", "margin": "8mm"}
    screen_number = _css_declarations(css, ".print-question-number")
    assert screen_number["display"] == "none"
    hidden = _css_declarations(css, "[hidden]")
    assert hidden["display"] == "none !important"
    catalog = _css_declarations(print_rules, ".catalog")
    assert catalog["columns"] == "2"
    assert catalog["column-gap"] == "2.5mm"
    section = _css_declarations(
        print_rules,
        ".catalog-group,\n  .catalog-section,\n  .card-grid,\n  .study-card-list",
    )
    assert section["display"] == "contents"
    card = _css_declarations(print_rules, ".principle-card")
    assert card["break-inside"] == "avoid"
    assert card["page-break-inside"] == "avoid"
    question = _css_declarations(print_rules, ".practice-question")
    assert question["grid-template-columns"] == "2.5em minmax(0, 1fr)"
    assert question["column-gap"] == "0.8mm"
    prompt = _css_declarations(print_rules, ".practice-question-text")
    assert prompt["font-size"] == "9pt"
    assert prompt["line-height"] == "1.32"
    choices = _css_declarations(print_rules, ".binary-choices")
    assert choices["line-height"] == "1.3"
    marker = _css_declarations(print_rules, ".choice-label::before")
    assert marker["content"] == '"□"'

    hidden = _css_declarations(
        print_rules,
        ".skip-link,\n"
        "  .site-header,\n"
        "  .controls,\n"
        "  .section-nav,\n"
        "  .section-heading,\n"
        "  .card-header,\n"
        "  .answer-disclosure,\n"
        "  .card-source,\n"
        "  .migration-notice,\n"
        "  .redistribution-index,\n"
        "  .empty-state,\n"
        "  .site-footer",
    )
    assert hidden["display"] == "none !important"
    assert ".answer-disclosure" in print_rules


def test_nested_404_uses_repository_absolute_asset_urls(tmp_path: Path) -> None:
    output = tmp_path / "site"
    base_url = "https://8pockets.github.io/first-class-architect/"
    build_site(output, base_url)
    html = (output / "404.html").read_text(encoding="utf-8")

    assert f'{base_url}assets/styles.css' in html
    assert f'{base_url}assets/catalog.js' in html


def test_public_projection_fails_closed_for_unknown_local_status() -> None:
    with pytest.raises(CatalogError, match="unknown local study status"):
        _coarse_status({"status": "preview", "stage": "day0"})


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("not_started", "unstarted"),
        ("learning", "learning"),
        ("failed_retest_due", "reviewing"),
        ("retained_14d", "retained_14d"),
    ],
)
def test_public_projection_uses_explicit_status_mapping(
    status: str,
    expected: str,
) -> None:
    assert _coarse_status({"status": status}) == expected


def test_build_refuses_to_replace_unmarked_directory(tmp_path: Path) -> None:
    output = tmp_path / "site"
    output.mkdir()
    (output / "keep.txt").write_text("owned by someone else", encoding="utf-8")

    with pytest.raises(ValueError, match="unmarked"):
        build_site(output, "https://8pockets.github.io/first-class-architect/")


def test_manifest_lists_only_local_yaml_section_files() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    sections = manifest["sections"]

    assert sections
    assert all(Path(section).suffix == ".yaml" for section in sections)
    assert all(not Path(section).is_absolute() for section in sections)
    assert all(".." not in Path(section).parts for section in sections)


def test_yaml_duplicate_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "public-progress.yaml"
    path.write_text(
        "version: 1\nitems:\n  S-K6-DUPLICATE: learning\n  S-K6-DUPLICATE: reviewing\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="invalid YAML"):
        load_public_progress(path)


def test_catalog_inventory_deletion_is_rejected(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    section = root / "01-overview.yaml"
    document = yaml.safe_load(section.read_text(encoding="utf-8"))
    document["principles"].pop(0)
    section.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="inventory total mismatch"):
        load_catalog(root / "manifest.yaml")


def test_question_choice_swap_without_independent_reaudit_is_rejected(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    section = root / "01-overview.yaml"
    document = yaml.safe_load(section.read_text(encoding="utf-8"))
    item = next(
        candidate
        for candidate in document["principles"]
        if candidate["editorial_status"] == "source_checked"
    )
    choices = item["question"]["choices"]
    choices["A"], choices["B"] = choices["B"], choices["A"]
    section.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="independently audited snapshot"):
        load_catalog(root / "manifest.yaml")


def test_physical_yaml_reordering_does_not_change_the_issued_display_order(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    section = root / "01-overview.yaml"
    document = yaml.safe_load(section.read_text(encoding="utf-8"))
    first, second = next(
        (left, right)
        for left, right in zip(
            document["principles"],
            document["principles"][1:],
        )
        if left.get("question") is not None and right.get("question") is not None
    )
    first["order"], second["order"] = second["order"], first["order"]
    section.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    catalog = load_catalog(root / "manifest.yaml")
    current = catalog.question_editions.editions[catalog.question_editions.current]

    assert [item.id for item in display_principles(catalog, published_only=True)] == [
        key for key, _ in sorted(current.assignments.items(), key=lambda entry: entry[1])
    ]


def test_source_checked_entry_without_a_question_is_rejected(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    section = root / "01-overview.yaml"
    _rewrite_item(section, source_checked=True)

    with pytest.raises(CatalogError, match="question is required"):
        load_catalog(root / "manifest.yaml")


def test_unpublished_entry_with_a_question_is_rejected(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    section = root / "01-overview.yaml"
    _rewrite_item(
        section,
        source_checked=False,
        question={
            "prompt": "柱脚形式の固定度について、正しい結論はどちらか。",
            "choices": {
                "A": "埋込み形式の固定度が最も高い",
                "B": "露出形式の固定度が最も高い",
            },
            "correct": "A",
        },
    )

    with pytest.raises(CatalogError, match="only allowed for source_checked"):
        load_catalog(root / "manifest.yaml")


@pytest.mark.parametrize(
    ("question", "error"),
    [
        ("この項目について説明しなさい。", "must be a mapping"),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "ボルト接合を含む"},
                "correct": "A",
            },
            "choices keys must be",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "ボルト接合を含む", "B": "溶接接合を含む"},
                "correct": "C",
            },
            "correct must be A or B",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "ボルト接合を含む", "B": "ボルト接合を含む"},
                "correct": "A",
            },
            "choices must be distinct",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "ボルト 接合を含む", "B": "ボルト  接合を含む"},
                "correct": "A",
            },
            "choices must be distinct",
        ),
        (
            {
                "prompt": "接合方法について説明しなさい。",
                "choices": {"A": "ボルト接合を含む", "B": "ボルト接合を含まない"},
                "correct": "A",
            },
            "must ask which conclusion is correct",
        ),
        (
            {
                "prompt": "誤っている説明と正しい結論はどちらか。",
                "choices": {"A": "ボルト接合を含む", "B": "ボルト接合を含まない"},
                "correct": "A",
            },
            "forbidden question form",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "必ずボルト接合を含む", "B": "ボルト接合を含まない"},
                "correct": "A",
            },
            "forbidden clue",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "両方", "B": "どちらでもない"},
                "correct": "A",
            },
            "forbidden clue",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "ボルト接合を含む（正解）", "B": "ボルト接合を含まない"},
                "correct": "A",
            },
            "reveal the answer",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "ボルト接合を含む（○）", "B": "ボルト接合を含まない"},
                "correct": "A",
            },
            "reveal the answer",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "ボルト接合を含む\u200b", "B": "ボルト接合を含まない"},
                "correct": "A",
            },
            "invisible characters",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "あ" * 41, "B": "接合方法に含まれない"},
                "correct": "A",
            },
            "40 characters or fewer",
        ),
        (
            {
                "prompt": "接合方法について、正しい結論はどちらか。",
                "choices": {"A": "含む", "B": "接合方法の一つとして分類に含まれている"},
                "correct": "A",
            },
            "similar in length",
        ),
    ],
)
def test_invalid_binary_question_is_rejected(
    tmp_path: Path,
    question: object,
    error: str,
) -> None:
    root = _copy_catalog(tmp_path)
    section = root / "01-overview.yaml"
    _rewrite_item(section, source_checked=True, question=question)

    with pytest.raises(CatalogError, match=error):
        load_catalog(root / "manifest.yaml")


def test_unknown_public_progress_id_fails_the_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "principle_catalog.site.load_public_progress",
        lambda: PublicProgressProjection(items={"S-K6-UNKNOWN": "learning"}),
    )

    with pytest.raises(ValueError, match="unknown IDs"):
        build_site(
            tmp_path / "site",
            "https://8pockets.github.io/first-class-architect/",
        )


def test_study_sync_appends_checked_items_without_changing_existing_state(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    existing = next(
        item for item in catalog.principles if item.editorial_status == "source_checked"
    )
    existing_record = {
        "id": existing.id,
        "title": "既存の題名を保持",
        "page": existing.source.pages[0],
        "status": "failed_retest_due",
        "retention_anchor": True,
        "stage": "day0_retest",
        "last_passed_on": None,
        "next_due_on": "2026-08-10",
        "consecutive_failures": 1,
    }
    unrelated_record = {
        "id": "S-E1-UNRELATED",
        "title": "別科目の既存項目",
        "status": "not_started",
    }
    state = {
        "version": 1,
        "items": [existing_record, unrelated_record],
        "queue": [{"item_id": existing.id}],
        "open_set": {"item_id": existing.id, "result_recorded": False},
    }
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    added = sync_study_items(path)
    updated = json.loads(path.read_text(encoding="utf-8"))
    checked_ids = {
        item.id
        for item in catalog.principles
        if item.editorial_status == "source_checked"
    }

    assert {item["id"] for item in updated["items"]} == checked_ids | {
        unrelated_record["id"]
    }
    assert updated["items"][0] == existing_record
    assert updated["items"][1] == unrelated_record
    assert updated["queue"] == state["queue"]
    assert updated["open_set"] == state["open_set"]
    assert set(added) == checked_ids - {existing.id}
    appended_ids = [item["id"] for item in updated["items"][2:]]
    appended_position = {item_id: index for index, item_id in enumerate(appended_ids)}
    by_id = {item.id: item for item in catalog.principles}
    for record in updated["items"][2:]:
        pages = by_id[record["id"]].source.pages
        assert record["page"] == (pages[0] if pages else None)
    assert any(record["page"] is None for record in updated["items"][2:]), (
        "externally sourced supplemental cards must sync without inventing a textbook page"
    )
    for item_id in appended_ids:
        for prerequisite in by_id[item_id].prerequisites:
            if prerequisite in appended_position:
                assert appended_position[prerequisite] < appended_position[item_id]
    assert sync_study_items(path) == ()


def test_public_progress_ignores_items_from_other_catalogs(tmp_path: Path) -> None:
    state = {
        "items": [
            {
                "id": "S-E1-UNRELATED",
                "status": "future_status_owned_by_another_catalog",
            }
        ]
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state), encoding="utf-8")

    assert public_progress_from_local(path) == {}


def test_public_progress_rejects_duplicate_local_ids(tmp_path: Path) -> None:
    item = next(
        item for item in load_catalog().principles if item.editorial_status == "source_checked"
    )
    state = {
        "items": [
            {"id": item.id, "status": "learning"},
            {"id": item.id, "status": "reviewing"},
        ]
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(CatalogError, match="duplicate study item"):
        public_progress_from_local(path)


def test_study_brief_always_shows_answer_and_three_points() -> None:
    item = next(
        item for item in load_catalog().principles if item.editorial_status == "source_checked" and item.type == "principle"
    )
    brief = study_brief(item.id)

    assert "## 確認問題（自作・2択）" in brief
    assert item.question is not None
    assert item.question.prompt in brief
    assert f"A. {item.question.choice_a}" in brief
    assert f"B. {item.question.choice_b}" in brief
    assert f"正解: **{item.question.correct}**" in brief
    assert "## 結論" in brief
    assert "## 理由" in brief
    assert "## 結論を左右する条件" in brief


def test_study_brief_keeps_an_empty_typed_third_facet_visible() -> None:
    catalog = load_catalog()
    item = next(
        candidate
        for candidate in catalog.principles
        if candidate.editorial_status == "source_checked"
        and not display_facets(catalog, candidate).tertiary.values
    )
    tertiary = display_facets(catalog, item).tertiary

    brief = study_brief(item.id)

    assert f"## {tertiary.label}\n\n—" in brief


def test_study_brief_reveal_is_a_backward_compatible_noop() -> None:
    item = next(
        item for item in load_catalog().principles if item.editorial_status == "source_checked" and item.type == "principle"
    )
    brief = study_brief(item.id, reveal=True)
    default = study_brief(item.id)

    assert brief == default
    assert "## 結論" in brief
    assert "## 理由" in brief
    assert "## 結論を左右する条件" in brief
    assert brief.index("## 確認問題（自作・2択）") < brief.index("正解:")
    assert brief.index("正解:") < brief.index("## 結論")
    assert item.question is not None
    assert item.question.prompt in brief
    assert f"A. {item.question.choice_a}" in brief
    assert f"B. {item.question.choice_b}" in brief
    assert f"正解: **{item.question.correct}**" in brief
    assert item.conclusion in brief
    assert item.reason in brief


def test_study_brief_cli_reveal_flag_keeps_the_same_visible_content() -> None:
    item = next(
        item for item in load_catalog().principles if item.editorial_status == "source_checked" and item.type == "principle"
    )
    hidden = subprocess.run(
        [sys.executable, "-m", "principle_catalog", "study-brief", item.id],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    revealed = subprocess.run(
        [
            sys.executable,
            "-m",
            "principle_catalog",
            "study-brief",
            item.id,
            "--reveal",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert hidden == revealed
    assert f"正解: **{item.question.correct}**" in hidden
    assert "## 結論" in hidden
    assert f"正解: **{item.question.correct}**" in revealed
    assert "## 結論" in revealed


def test_study_brief_rejects_items_without_a_source_checked_question(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = load_catalog()
    item = replace(catalog.principles[0], editorial_status="source_gap", question=None)
    fixture_catalog = replace(catalog, principles=(item, *catalog.principles[1:]))
    monkeypatch.setattr("principle_catalog.study.load_catalog", lambda: fixture_catalog)

    with pytest.raises(CatalogError, match="not source-checked"):
        study_brief(item.id)
