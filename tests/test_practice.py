from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from principle_catalog.catalog import CatalogError, load_catalog
from principle_catalog.practice import PRACTICE_PATH, load_practice, render_practice


def _variant_rows():
    return [variant for rows in load_practice(load_catalog()).values() for variant in rows]


def _write_practice(tmp_path: Path, mutate) -> Path:
    document = yaml.safe_load(PRACTICE_PATH.read_text(encoding="utf-8"))
    mutate(document)
    path = tmp_path / "practice.yaml"
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_practice_has_separate_stable_identity_and_source_bounded_content() -> None:
    catalog = load_catalog()
    grouped = load_practice(catalog)
    rows = [variant for variants in grouped.values() for variant in variants]
    parents = {item.id: item for item in catalog.principles}

    assert len(catalog.principles) == 311
    assert len(rows) == 6
    assert len({row.item_id for row in rows}) == 6
    assert sum(row.figure is not None for row in rows) == 3
    assert sum(row.correct == "A" for row in rows) == 3
    for row in rows:
        assert row.item_id.startswith(f"practice:{parents[row.parent_id].code}:")
        assert re.fullmatch(r"[a-zA-Z0-9._:-]{1,200}", row.item_id)
        assert re.fullmatch(r"[0-9a-f]{64}", row.revision)
        assert row.parent_id not in {row.item_id}
        assert set(row.source_pages) <= set(parents[row.parent_id].source.pages)


@pytest.mark.parametrize("field,value,match", [
    ("parent_id", "S-K6-UNKNOWN", "parent_id"),
    ("source_pages", [999], "source_pages"),
    ("source_pages", [True], "source_pages"),
    ("source_pages", [189, 189], "source_pages"),
    ("figure", "<svg onload=alert(1)>", "figure"),
    ("figure", [], "figure"),
    ("correct", "C", "correct label"),
    ("id", 'bad\" onload=\"x', "stable slug"),
    ("choices", {"A": "同じ", "B": "同じ"}, "distinct choices"),
    ("choices", {"A": "答え"}, "non-empty A and B"),
])
def test_practice_rejects_invalid_contract(tmp_path, field, value, match) -> None:
    path = _write_practice(tmp_path, lambda doc: doc["variants"][0].__setitem__(field, value))
    with pytest.raises(CatalogError, match=match):
        load_practice(load_catalog(), path)


def test_practice_rejects_duplicate_ids_and_unexpected_fields(tmp_path) -> None:
    duplicate = _write_practice(tmp_path, lambda doc: doc["variants"].append(doc["variants"][0]))
    with pytest.raises(CatalogError, match="unique stable slug"):
        load_practice(load_catalog(), duplicate)
    unknown = _write_practice(tmp_path, lambda doc: doc["variants"][0].__setitem__("raw_svg", "<svg>"))
    with pytest.raises(CatalogError, match="unexpected fields"):
        load_practice(load_catalog(), unknown)


def test_practice_rejects_duplicate_yaml_keys(tmp_path) -> None:
    path = tmp_path / "practice.yaml"
    path.write_text("version: 1\nversion: 1\nvariants: []\n", encoding="utf-8")
    with pytest.raises(CatalogError, match="invalid YAML"):
        load_practice(load_catalog(), path)


def test_practice_revision_changes_only_changed_variant(tmp_path) -> None:
    catalog = load_catalog()
    before = {row.id: row for rows in load_practice(catalog).values() for row in rows}
    path = _write_practice(tmp_path, lambda doc: doc["variants"][0].__setitem__("explanation", "計算の説明を変更。"))
    after = {row.id: row for rows in load_practice(catalog, path).values() for row in rows}
    changed = {key for key in before if before[key].revision != after[key].revision}
    assert changed == {"fillet-area-different-values"}
    assert all(before[key].item_id == after[key].item_id for key in before)


def test_practice_markup_is_optional_separate_accessible_and_escaped() -> None:
    rows = _variant_rows()
    markup = "".join(render_practice(row) for row in rows)
    assert markup.count("data-practice-panel") == 6
    assert markup.count("data-practice-choice=") == 12
    assert markup.count("data-practice-answer") == 6
    assert markup.count('role="img"') == 3
    assert "本体の成績とは別" in markup
    assert "data-study-id=" not in markup
    assert 'data-answer-choice=' not in markup
    ids = re.findall(r'\sid="([^"]+)"', markup)
    assert len(ids) == len(set(ids))
    assert all(target in ids for target in re.findall(r'aria-controls="([^"]+)"', markup))
    assert all(target in ids for target in re.findall(r'aria-labelledby="([^"]+)"', markup))
    malicious = replace(rows[0], title='<img src=x onerror="alert(1)">',
                        prompt="<script>bad()</script>", explanation="A & B < C")
    escaped = render_practice(malicious)
    assert "<script>" not in escaped
    assert "<img" not in escaped
    assert "&lt;script&gt;" in escaped
    assert "A &amp; B &lt; C" in escaped
    with pytest.raises(CatalogError, match="reviewed template"):
        render_practice(replace(rows[0], figure="<svg>"))


def test_main_explanations_include_worked_lines_and_actual_distinctions() -> None:
    catalog = load_catalog()
    items = {item.id: item for item in catalog.principles}
    area = items["S-K6-FILLET-WELD-EFFECTIVE-AREA"].display_content
    length = items["S-K6-FILLET-WELD-EFFECTIVE-LENGTH"].display_content
    throat = items["S-K6-FILLET-WELD-SIZE-EFFECTIVE-THROAT"].display_content
    assert "100mm×4.2mm＝420mm²" in " ".join(area.numbers_exceptions)
    assert "132−2×6＝120mm" in " ".join(length.numbers_exceptions)
    assert length.rule not in length.numbers_exceptions
    assert "0.7×6mm＝4.2mm" in " ".join(throat.numbers_exceptions)
    for item_id in ("S-K6-WELD-DEFECT-BLOWHOLE", "S-K6-WELD-DEFECT-PIT"):
        explanation = " ".join(items[item_id].display_content.confusable_points)
        assert "内部" in explanation
        assert "表面" in explanation
        assert "開口" in explanation
