from __future__ import annotations

import json
import re
import shutil
import unicodedata
from html import escape
from pathlib import Path

import pytest
import yaml

from principle_catalog.catalog import (
    CATALOG_ROOT,
    CatalogError,
    MANIFEST_PATH,
    PUBLIC_PROGRESS_PATH,
    load_catalog,
    load_public_progress,
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


def test_manifest_covers_every_requested_pdf_page() -> None:
    catalog = load_catalog()

    assert catalog.manifest.source_sha256 == EXPECTED_SHA256
    assert catalog.manifest.first_page == 158
    assert catalog.manifest.last_page == 215
    assert catalog.manifest.audited_pages == tuple(range(158, 216))
    assert catalog.audit.table_pages == tuple(range(159, 176))
    assert catalog.audit.table_row_count == 167
    assert len(catalog.audit.primary_question_codes) == 167


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
    catalog_ids = {item.id for item in load_catalog().principles}
    state = json.loads(LOCAL_STUDY_STATE.read_text(encoding="utf-8"))
    study_ids = {
        item["id"] for item in state["items"] if item["id"].startswith("S-K6-")
    }

    assert study_ids <= catalog_ids


def test_source_checked_entries_have_complete_question_and_three_point_content() -> None:
    checked = [
        item for item in load_catalog().principles if item.editorial_status == "source_checked"
    ]

    assert len(checked) == 116
    for item in checked:
        assert item.principle
        assert item.question
        assert "結論" in item.question
        assert "理由" in item.question
        assert "条件" in item.question
        assert item.question != item.conclusion
        assert item.conclusion
        assert item.reason != "教材に記載なし"
        assert item.conditions
        assert "教材に記載なし" not in item.conditions

    normalized_questions = {
        unicodedata.normalize("NFKC", item.question).casefold().strip()
        for item in checked
        if item.question is not None
    }
    assert len(normalized_questions) == 116


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
    assert html.count("確認問題（自作）") == published
    assert all(item.principle in html for item in expected_published)
    assert all(item.question in html for item in expected_published)
    assert all(f'id="{item.id}"' not in html for item in unpublished)


def test_build_places_each_question_before_its_three_point_answer_and_searches_it(
    tmp_path: Path,
) -> None:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    html = (output / "index.html").read_text(encoding="utf-8")
    published = [
        item
        for item in load_catalog().principles
        if item.editorial_status == "source_checked"
    ]

    for item in published:
        assert item.question is not None
        card = html.split(f'id="{item.id}"', maxsplit=1)[1].split(
            "</article>", maxsplit=1
        )[0]
        question = escape(item.question)
        search_text = card.split('data-search="', maxsplit=1)[1].split('"', maxsplit=1)[0]
        question_opening = card.split('<div class="practice-question"', maxsplit=1)[
            1
        ].split(">", maxsplit=1)[0]

        heading = f"<h3>{escape(item.principle)}</h3>"
        assert card.index(heading) < card.index('<div class="practice-question"')
        assert card.index('<div class="practice-question"') < card.index(
            "<dt>結論</dt>"
        )
        assert card.index("<dt>結論</dt>") < card.index("<dt>理由</dt>")
        assert card.index("<dt>理由</dt>") < card.index(
            "<dt>結論を左右する条件</dt>"
        )
        assert "hidden" not in question_opening
        assert "<details" not in card
        assert question in card
        assert escape(item.question.lower()) in search_text


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
    assert "fetch(" not in script
    assert "localStorage" not in script
    assert "http://" not in html + script + css
    assert "https://" not in script + css


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


def test_source_checked_entry_without_a_question_is_rejected(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    section = root / "01-overview.yaml"
    text, replacements = re.subn(r"\n  question: [^\n]+", "", section.read_text(), count=1)
    assert replacements == 1
    section.write_text(text, encoding="utf-8")

    with pytest.raises(CatalogError, match="question is required"):
        load_catalog(root / "manifest.yaml")


def test_unpublished_entry_with_a_question_is_rejected(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    section = root / "01-overview.yaml"
    text = section.read_text(encoding="utf-8")
    target = "  principle: 柱脚形式と固定度の大小\n"
    replacement = (
        f"{target}"
        "  question: 柱脚形式について、結論、その理由及び結論を左右する条件を説明しなさい。\n"
    )
    assert target in text
    section.write_text(text.replace(target, replacement, 1), encoding="utf-8")

    with pytest.raises(CatalogError, match="only allowed for source_checked"):
        load_catalog(root / "manifest.yaml")


def test_question_without_all_three_requested_parts_is_rejected(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    section = root / "01-overview.yaml"
    text, replacements = re.subn(
        r"\n  question: [^\n]+",
        "\n  question: この項目について説明しなさい。",
        section.read_text(encoding="utf-8"),
        count=1,
    )
    assert replacements == 1
    section.write_text(text, encoding="utf-8")

    with pytest.raises(CatalogError, match="conclusion, reason, and conditions"):
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


def test_study_brief_shows_the_question_before_the_three_point_answer() -> None:
    item = next(
        item for item in load_catalog().principles if item.editorial_status == "source_checked"
    )
    brief = study_brief(item.id)

    assert "## 確認問題（自作）" in brief
    assert "## 結論" in brief
    assert "## 理由" in brief
    assert "## 結論を左右する条件" in brief
    assert brief.index("## 確認問題（自作）") < brief.index("## 結論")
    assert item.question in brief
    assert item.conclusion in brief
    assert item.reason in brief


def test_study_brief_rejects_items_without_a_source_checked_question() -> None:
    item = next(
        item for item in load_catalog().principles if item.editorial_status != "source_checked"
    )

    with pytest.raises(CatalogError, match="not source-checked"):
        study_brief(item.id)
