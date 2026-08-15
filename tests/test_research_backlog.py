from __future__ import annotations

from pathlib import Path

import yaml

from principle_catalog.catalog import load_catalog


BACKLOG_PATH = Path("data/principles/steel/research-backlog.yaml")


def _backlog() -> dict[str, object]:
    loaded = yaml.safe_load(BACKLOG_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_public_coverage_backlog_is_the_exact_unpublished_primary_code_gap() -> None:
    catalog = load_catalog()
    backlog = _backlog()["public_coverage_backlog"]
    assert isinstance(backlog, dict)
    codes = backlog["primary_question_codes"]
    assert isinstance(codes, list)

    published_codes = {
        code
        for item in catalog.principles
        if item.editorial_status == "source_checked"
        for code in item.source.question_codes
    }
    expected = [
        code
        for code in catalog.audit.primary_question_codes
        if code not in published_codes
    ]

    assert backlog["priority"] == 1
    assert backlog["count"] == len(codes) == 30
    assert codes == expected
    assert len(codes) == len(set(codes))


def test_topic_backlog_is_exactly_the_private_fire_and_special_load_group() -> None:
    catalog = load_catalog()
    backlog = _backlog()["topic_backlog"]
    assert isinstance(backlog, dict)
    subtopics = backlog["subtopics"]
    keys = backlog["keys"]
    assert isinstance(subtopics, list)
    assert isinstance(keys, list)

    fire_group = next(
        group for group in catalog.taxonomy.groups if group.id == "steel.fire-special"
    )
    expected_subtopics = [subtopic.id for subtopic in fire_group.subtopics]
    expected_keys = [
        item.id
        for item in catalog.principles
        if catalog.taxonomy.assignments[item.id] in set(expected_subtopics)
    ]

    assert backlog["priority"] == 2
    assert subtopics == expected_subtopics
    assert set(keys) == set(expected_keys)
    assert all(
        item.editorial_status != "source_checked"
        for item in catalog.principles
        if item.id in set(keys)
    )


def test_authoritative_source_backlog_uses_allowed_sources_and_private_keys() -> None:
    catalog = load_catalog()
    data = _backlog()
    policy = data["policy"]
    backlog = data["authoritative_source_backlog"]
    assert isinstance(policy, dict)
    assert isinstance(backlog, dict)
    keys = backlog["keys"]
    assert isinstance(keys, list)
    by_key = {item.id: item for item in catalog.principles}

    assert policy["allowed_source_kinds"] == list(
        catalog.manifest.authoritative_source_schema.allowed_kinds
    )
    assert policy["unresolved_publication"] == "keep_private"
    assert backlog["priority"] == 4
    assert backlog["required_supports"] == [
        "statement",
        "explanation",
        "conditions",
    ]
    assert len(keys) == len(set(keys)) == 3
    assert all(by_key[key].editorial_status == "source_gap" for key in keys)
    assert all(not by_key[key].source.authoritative_sources for key in keys)


def test_atomicity_source_gap_is_kept_private_until_all_supports_are_found() -> None:
    catalog = load_catalog()
    backlog = _backlog()["source_gap_backlog"]
    assert isinstance(backlog, dict)
    keys = backlog["keys"]
    assert isinstance(keys, list)
    by_key = {item.id: item for item in catalog.principles}

    assert backlog["priority"] == 3
    assert backlog["required_supports"] == [
        "statement",
        "explanation",
        "conditions",
    ]
    assert keys == ["S-K6-BRACED-FRAME-COLUMN-BRACE-CAPACITY-SUM"]
    assert by_key[keys[0]].editorial_status == "source_gap"
    assert "P170" in by_key[keys[0]].reason
    assert "P200〜204" in by_key[keys[0]].reason
