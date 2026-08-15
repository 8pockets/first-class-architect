from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Callable

import pytest
import yaml

from principle_catalog.catalog import (
    CATALOG_ROOT,
    CatalogError,
    display_facets,
    display_principles,
    load_catalog,
    validate_question_edition_history,
)
from principle_catalog.models import (
    IdentificationDisplayContent,
    RuleDisplayContent,
)


def _edition_digest(assignments: dict[str, int]) -> str:
    canonical = json.dumps(
        [
            {"key": key, "number": number}
            for key, number in sorted(assignments.items(), key=lambda item: item[1])
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _find_section_item(
    root: Path,
    predicate: Callable[[dict[str, object]], bool],
) -> tuple[Path, dict[str, object], dict[str, object]]:
    manifest = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
    for relative in manifest["sections"]:
        section_path = root / relative
        section = yaml.safe_load(section_path.read_text(encoding="utf-8"))
        for item in section["principles"]:
            if predicate(item):
                return section_path, section, item
    raise AssertionError("matching catalog item not found")


def test_display_taxonomy_assigns_every_active_card_once_to_7_by_37_tree() -> None:
    catalog = load_catalog()
    taxonomy = catalog.taxonomy
    subtopics = [
        subtopic
        for group in taxonomy.groups
        for subtopic in group.subtopics
    ]

    assert len(taxonomy.groups) == 7
    assert len(subtopics) == 37
    assert set(taxonomy.assignments) == {item.id for item in catalog.principles}
    assert len(taxonomy.assignments) == len(catalog.principles)
    assert set(taxonomy.assignments.values()) == {
        subtopic.id for subtopic in subtopics
    }
    assert [group.order for group in taxonomy.groups] == list(range(1, 8))
    for group in taxonomy.groups:
        assert [subtopic.order for subtopic in group.subtopics] == list(
            range(1, len(group.subtopics) + 1)
        )


def test_physical_source_collection_is_not_used_as_display_taxonomy() -> None:
    catalog = load_catalog()
    formerly_cross_cutting = next(
        item for item in catalog.principles if item.section_id == "K6-00"
    )

    assert formerly_cross_cutting.section_title == "本試験知識（横断）"
    assert catalog.taxonomy.assignments[formerly_cross_cutting.id].startswith(
        "steel."
    )
    assert catalog.taxonomy.assignments[formerly_cross_cutting.id] != (
        formerly_cross_cutting.section_id
    )


def test_display_order_is_deterministic_and_prerequisite_first() -> None:
    catalog = load_catalog()

    ordered = display_principles(catalog)
    repeated = display_principles(catalog)
    positions = {item.id: index for index, item in enumerate(ordered)}
    subtopic_ranks = {
        subtopic.id: (group.order, subtopic.order)
        for group in catalog.taxonomy.groups
        for subtopic in group.subtopics
    }
    ordered_ranks = [
        subtopic_ranks[catalog.taxonomy.assignments[item.id]] for item in ordered
    ]

    assert ordered == repeated
    assert {item.id for item in ordered} == {item.id for item in catalog.principles}
    assert ordered_ranks == sorted(ordered_ranks)
    for item in ordered:
        assert all(
            positions[prerequisite] < positions[item.id]
            for prerequisite in item.prerequisites
        )


def test_current_question_edition_covers_each_published_card_once() -> None:
    catalog = load_catalog()
    editions = catalog.question_editions
    current = editions.editions[editions.current]
    published = {
        item.id
        for item in catalog.principles
        if item.editorial_status == "source_checked"
    }

    assert editions.current == "K6-R2"
    assert current.status == "current"
    assert len(catalog.principles) == 216
    assert len(published) == 116
    assert len(editions.editions["K6-R1"].assignments) == 116
    assert set(current.assignments) == published
    assert set(current.assignments.values()) == set(range(1, len(published) + 1))
    assert len(current.content_sha256) == 64
    assert editions.editions["K6-R1"].status == "archived"
    by_key = {item.id: item for item in catalog.principles}
    for key in published:
        assert all(
            current.assignments[prerequisite] < current.assignments[key]
            for prerequisite in by_key[key].prerequisites
        )
    assert [item.id for item in display_principles(catalog, published_only=True)] == [
        key for key, _ in sorted(current.assignments.items(), key=lambda entry: entry[1])
    ]


def test_archived_question_edition_can_reference_a_retired_key() -> None:
    catalog = load_catalog()
    archived = catalog.question_editions.editions["K6-R1"]

    assert set(archived.assignments) & set(catalog.migration.retired)


def test_question_edition_history_rejects_rewriting_a_past_assignment(
    tmp_path: Path,
) -> None:
    previous = tmp_path / "previous.yaml"
    current = tmp_path / "current.yaml"
    source = CATALOG_ROOT / "question-editions.yaml"
    shutil.copy2(source, previous)
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    assignments = document["editions"]["K6-R1"]["assignments"]
    first, second = list(assignments)[:2]
    assignments[first], assignments[second] = assignments[second], assignments[first]
    document["editions"]["K6-R1"]["content_sha256"] = _edition_digest(assignments)
    current.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="past question edition"):
        validate_question_edition_history(previous, current)


def test_taxonomy_change_requires_its_own_audit_hash(tmp_path: Path) -> None:
    root = tmp_path / "steel"
    shutil.copytree(CATALOG_ROOT, root)
    taxonomy_path = root / "taxonomy.yaml"
    document = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
    document["groups"][0]["title"] += "変更"
    taxonomy_path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="taxonomy.*audited snapshot"):
        load_catalog(root / "manifest.yaml")


def test_question_order_has_its_own_audit_hash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "steel"
    shutil.copytree(CATALOG_ROOT, root)
    manifest_path = root / "manifest.yaml"
    document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    document["question_audit"]["order_sha256"] = "0" * 64
    manifest_path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="question order.*audited snapshot"):
        load_catalog(manifest_path)


def test_prerequisite_change_requires_only_its_audit_hash(tmp_path: Path) -> None:
    root = tmp_path / "steel"
    shutil.copytree(CATALOG_ROOT, root)
    manifest = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
    changed = False
    for relative in manifest["sections"]:
        section_path = root / relative
        section = yaml.safe_load(section_path.read_text(encoding="utf-8"))
        item = next(
            (
                item
                for item in section["principles"]
                if item.get("prerequisites")
            ),
            None,
        )
        if item is None:
            continue
        item["prerequisites"] = item["prerequisites"][:-1]
        section_path.write_text(
            yaml.safe_dump(section, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        changed = True
        break
    assert changed

    with pytest.raises(CatalogError, match="prerequisites.*audited snapshot"):
        load_catalog(root / "manifest.yaml")


def test_physical_collection_reordering_does_not_change_semantic_audits(
    tmp_path: Path,
) -> None:
    root = tmp_path / "steel"
    shutil.copytree(CATALOG_ROOT, root)
    manifest = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
    changed = False
    for relative in manifest["sections"]:
        section_path = root / relative
        section = yaml.safe_load(section_path.read_text(encoding="utf-8"))
        checked = [
            item
            for item in section["principles"]
            if item["editorial_status"] == "source_checked"
        ]
        if len(checked) < 2:
            continue
        checked[0]["order"], checked[1]["order"] = (
            checked[1]["order"],
            checked[0]["order"],
        )
        section_path.write_text(
            yaml.safe_dump(section, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        changed = True
        break
    assert changed

    reordered = load_catalog(root / "manifest.yaml")

    assert reordered.manifest.question_audit_sha256 == (
        load_catalog().manifest.question_audit_sha256
    )


def test_source_model_exposes_pdf_and_optional_authoritative_source_kinds() -> None:
    catalog = load_catalog()

    assert all("pdf" in item.source.kinds for item in catalog.principles)
    assert all(
        source.supports
        for item in catalog.principles
        for source in item.source.authoritative_sources
    )
    assert all(item.verification.statement_source for item in catalog.principles)
    assert all(item.verification.explanation_completeness for item in catalog.principles)


def test_every_published_rule_and_identification_has_typed_display_content() -> None:
    catalog = load_catalog()
    typed_items = [
        item
        for item in catalog.principles
        if item.editorial_status == "source_checked"
        and item.type in {"rule", "identification"}
    ]

    assert typed_items
    for item in typed_items:
        facets = display_facets(catalog, item)
        assert facets.typed
        assert facets.primary.values
        assert facets.secondary.values
        if item.type == "rule":
            assert isinstance(item.display_content, RuleDisplayContent)
            assert (
                facets.primary.label,
                facets.secondary.label,
                facets.tertiary.label,
            ) == ("規定", "適用範囲", "数値・例外")
        else:
            assert isinstance(item.display_content, IdentificationDisplayContent)
            assert (
                facets.primary.label,
                facets.secondary.label,
                facets.tertiary.label,
            ) == ("定義", "識別条件", "混同注意")


def test_unpublished_untyped_item_keeps_generic_labels() -> None:
    catalog = load_catalog()
    item = next(
        item
        for item in catalog.principles
        if item.editorial_status != "source_checked"
        and item.type in {"rule", "identification"}
        and item.display_content is None
    )

    facets = display_facets(catalog, item)

    assert not facets.typed
    assert (
        facets.primary.label,
        facets.secondary.label,
        facets.tertiary.label,
    ) == ("結論", "理由", "結論を左右する条件")
    assert facets.secondary.values == (item.reason,)


def test_published_typed_display_content_is_required_and_exact(tmp_path: Path) -> None:
    root = tmp_path / "steel"
    shutil.copytree(CATALOG_ROOT, root)
    section_path, section, item = _find_section_item(
        root,
        lambda candidate: candidate["editorial_status"] == "source_checked"
        and candidate["type"] == "rule",
    )
    item.pop("display_content")
    section_path.write_text(
        yaml.safe_dump(section, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="display_content is required"):
        load_catalog(root / "manifest.yaml")

    shutil.rmtree(root)
    shutil.copytree(CATALOG_ROOT, root)
    section_path, section, item = _find_section_item(
        root,
        lambda candidate: candidate["editorial_status"] == "source_checked"
        and candidate["type"] == "identification",
    )
    item["display_content"]["reason"] = "誤った共通フィールド"
    section_path.write_text(
        yaml.safe_dump(section, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="display_content keys must be"):
        load_catalog(root / "manifest.yaml")


def test_typed_display_content_change_requires_content_reaudit(tmp_path: Path) -> None:
    root = tmp_path / "steel"
    shutil.copytree(CATALOG_ROOT, root)
    section_path, section, item = _find_section_item(
        root,
        lambda candidate: candidate["editorial_status"] == "source_checked"
        and candidate["type"] == "rule",
    )
    item["display_content"]["rule"] += "変更"
    section_path.write_text(
        yaml.safe_dump(section, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="question content.*audited snapshot"):
        load_catalog(root / "manifest.yaml")


def test_optional_authoritative_source_and_review_fields_are_loaded(
    tmp_path: Path,
) -> None:
    root = tmp_path / "steel"
    shutil.copytree(CATALOG_ROOT, root)
    manifest = yaml.safe_load((root / "manifest.yaml").read_text(encoding="utf-8"))
    selected: dict[str, object] | None = None
    selected_path: Path | None = None
    for relative in manifest["sections"]:
        section_path = root / relative
        section = yaml.safe_load(section_path.read_text(encoding="utf-8"))
        selected = next(
            (
                item
                for item in section["principles"]
                if item["editorial_status"] == "source_gap"
            ),
            None,
        )
        if selected is not None:
            selected_path = section_path
            break
    assert selected is not None and selected_path is not None
    selected["source"]["authoritative_sources"] = [
        {
            "kind": "law",
            "title": "建築基準法",
            "locator": "第1条",
            "url": "https://example.go.jp/law/1",
            "supports": ["statement", "conditions"],
        }
    ]
    selected["verification"] = {
        "statement_source": "verified",
        "explanation_completeness": "partial",
        "conditions_completeness": "complete",
    }
    section = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
    replacement = next(
        item for item in section["principles"] if item["id"] == selected["id"]
    )
    replacement.update(selected)
    selected_path.write_text(
        yaml.safe_dump(section, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    item = next(
        item
        for item in load_catalog(root / "manifest.yaml").principles
        if item.id == selected["id"]
    )

    assert item.source.kinds == ("pdf", "law")
    assert item.source.authoritative_sources[0].supports == (
        "statement",
        "conditions",
    )
    assert item.verification.statement_source == "verified"
    assert item.verification.explanation_completeness == "partial"
