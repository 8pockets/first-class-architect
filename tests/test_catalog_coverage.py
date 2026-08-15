from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from principle_catalog.catalog import (
    CATALOG_ROOT,
    COVERAGE_TIERS_PATH,
    coverage_assignment,
    coverage_introduction_order,
    coverage_principles,
    display_principles,
    load_catalog,
    validate_coverage_tier_history,
)
from principle_catalog.study import new_study_candidates, unlocked_coverage_tier


def _write_yaml(path: Path, document: object) -> None:
    path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _copy_catalog(tmp_path: Path) -> Path:
    root = tmp_path / "steel"
    shutil.copytree(CATALOG_ROOT, root)
    return root


def _scheme_digest(scheme: dict[str, object]) -> str:
    assignments = scheme["assignments"]
    assert isinstance(assignments, dict)
    payload = {
        "constraints": scheme["constraints"],
        "assignments": [
            {
                "key": key,
                "tier": assignment["tier"],
                "introduction_order": assignment["introduction_order"],
                "reasons": assignment["reasons"],
            }
            for key, assignment in sorted(
                assignments.items(),
                key=lambda item: item[1]["introduction_order"],
            )
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _refresh_scheme_digest(scheme: dict[str, object]) -> None:
    scheme["content_sha256"] = _scheme_digest(scheme)


def test_coverage_views_are_cumulative_filters_of_the_existing_display_order() -> None:
    catalog = load_catalog()
    published = display_principles(catalog, published_only=True)

    foundation = coverage_principles(catalog, ceiling=1)
    standard = coverage_principles(catalog, ceiling=2)
    all_coverage = coverage_principles(catalog)

    assert len(foundation) == 32
    assert len(standard) == 74
    assert len(all_coverage) == 116
    assert all_coverage == published
    assert foundation == tuple(
        item for item in published if coverage_assignment(catalog, item).tier == 1
    )
    assert standard == tuple(
        item for item in published if coverage_assignment(catalog, item).tier <= 2
    )
    assert coverage_principles(catalog, ceiling=2, exclusive=True) == tuple(
        item for item in published if coverage_assignment(catalog, item.id).tier == 2
    )


def test_manifest_uses_the_fixed_independently_audited_coverage_projection() -> None:
    catalog = load_catalog()

    assert catalog.manifest.projection_paths["coverage_tiers"] == (
        CATALOG_ROOT / "coverage-tiers.yaml"
    )
    assert len(catalog.manifest.coverage_tiers_audit_sha256) == 64
    assert catalog.coverage.current == "steel-coverage-v1"
    assert {
        tier: (definition.slug, definition.label)
        for tier, definition in catalog.coverage.tiers.items()
    } == {
        1: ("foundation", "骨格"),
        2: ("standard", "標準"),
        3: ("advanced", "発展"),
    }


def test_current_coverage_scheme_records_the_agreed_balancing_constraints() -> None:
    catalog = load_catalog()
    scheme = catalog.coverage.schemes[catalog.coverage.current]

    assert scheme.constraints.tier_counts == {1: 32, 2: 42, 3: 42}
    assert scheme.constraints.answer_counts == {
        1: {"A": 16, "B": 16},
        2: {"A": 21, "B": 21},
        3: {"A": 21, "B": 21},
    }
    assert scheme.constraints.type_counts[1] == {
        "principle": 19,
        "rule": 7,
        "identification": 6,
    }
    assert scheme.constraints.max_same_answer_run == 3
    assert scheme.constraints.foundation_covers_all_published_subtopics is True
    assert sorted(
        assignment.introduction_order
        for assignment in scheme.assignments.values()
    ) == list(range(1, 117))


def test_manifest_rejects_coverage_projection_path_substitution(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    shadow = root / "shadow-coverage-tiers.yaml"
    shutil.copyfile(root / "coverage-tiers.yaml", shadow)
    manifest_path = root / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["projections"]["coverage_tiers"] = shadow.name
    _write_yaml(manifest_path, manifest)

    with pytest.raises(
        ValueError,
        match="projections.coverage_tiers must be coverage-tiers.yaml",
    ):
        load_catalog(manifest_path)


def test_catalog_rejects_unknown_coverage_reasons(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    first = min(
        scheme["assignments"].values(),
        key=lambda assignment: assignment["introduction_order"],
    )
    first["reasons"] = ["personal_difficulty"]
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="reasons are invalid"):
        load_catalog(root / "manifest.yaml")


def test_catalog_rejects_coverage_assignment_changed_without_scheme_digest(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    assignment = next(iter(scheme["assignments"].values()))
    replacement = next(
        reason
        for reason in (
            "coverage_representative",
            "prerequisite",
            "standard_application",
            "basic_identification",
            "exception_detail",
            "integrated_judgment",
        )
        if reason not in assignment["reasons"]
    )
    assignment["reasons"].append(replacement)
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="differs from its audited snapshot"):
        load_catalog(root / "manifest.yaml")


def test_catalog_rejects_noncontiguous_coverage_introduction_order(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    ordered = sorted(
        scheme["assignments"].values(),
        key=lambda assignment: assignment["introduction_order"],
    )
    ordered[1]["introduction_order"] = ordered[0]["introduction_order"]
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="introduction order must be unique and contiguous"):
        load_catalog(root / "manifest.yaml")


def test_catalog_rejects_coverage_projection_without_independent_audit(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    manifest_path = root / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["question_audit"]["coverage_tiers_sha256"] = "0" * 64
    _write_yaml(manifest_path, manifest)

    with pytest.raises(
        ValueError,
        match="coverage tiers differ from the independently audited snapshot",
    ):
        load_catalog(manifest_path)


def test_current_coverage_scheme_must_assign_every_published_question(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    key = max(
        scheme["assignments"],
        key=lambda candidate: scheme["assignments"][candidate][
            "introduction_order"
        ],
    )
    del scheme["assignments"][key]
    _refresh_scheme_digest(scheme)
    _write_yaml(path, document)

    with pytest.raises(
        ValueError,
        match="must assign every published question exactly once",
    ):
        load_catalog(root / "manifest.yaml")


def test_same_tier_prerequisites_must_be_introduced_first(tmp_path: Path) -> None:
    catalog = load_catalog()
    current = catalog.coverage.schemes[catalog.coverage.current]
    by_id = {item.id: item for item in catalog.principles}
    dependent, prerequisite = next(
        (item.id, prerequisite)
        for item in catalog.principles
        for prerequisite in item.prerequisites
        if item.id in current.assignments
        and prerequisite in current.assignments
        and current.assignments[item.id].tier
        == current.assignments[prerequisite].tier
    )

    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    assignments = scheme["assignments"]
    assignments[dependent]["introduction_order"], assignments[prerequisite][
        "introduction_order"
    ] = (
        assignments[prerequisite]["introduction_order"],
        assignments[dependent]["introduction_order"],
    )
    assert by_id[dependent].prerequisites
    _refresh_scheme_digest(scheme)
    _write_yaml(path, document)

    with pytest.raises(
        ValueError,
        match="must introduce same-tier prerequisite first",
    ):
        load_catalog(root / "manifest.yaml")


def test_prerequisite_cannot_be_in_a_later_coverage_tier(tmp_path: Path) -> None:
    catalog = load_catalog()
    current = catalog.coverage.schemes[catalog.coverage.current]
    by_id = {item.id: item for item in catalog.principles}
    prerequisite, dependent = next(
        (prerequisite, item.id)
        for item in catalog.principles
        for prerequisite in item.prerequisites
        if item.id in current.assignments
        and prerequisite in current.assignments
        and current.assignments[prerequisite].tier
        < current.assignments[item.id].tier
        and by_id[prerequisite].type == item.type
        and by_id[prerequisite].question is not None
        and item.question is not None
        and by_id[prerequisite].question.correct == item.question.correct
        and catalog.taxonomy.assignments[prerequisite]
        == catalog.taxonomy.assignments[item.id]
    )

    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    assignments = scheme["assignments"]
    assignments[prerequisite]["tier"], assignments[dependent]["tier"] = (
        assignments[dependent]["tier"],
        assignments[prerequisite]["tier"],
    )
    assignments[prerequisite]["introduction_order"], assignments[dependent][
        "introduction_order"
    ] = (
        assignments[dependent]["introduction_order"],
        assignments[prerequisite]["introduction_order"],
    )
    _refresh_scheme_digest(scheme)
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="prerequisite in a later coverage tier"):
        load_catalog(root / "manifest.yaml")


def test_coverage_answer_targets_are_validated_against_questions(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    counts = scheme["constraints"]["answer_counts"][1]
    counts["A"] -= 1
    counts["B"] += 1
    _refresh_scheme_digest(scheme)
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="answer counts do not match"):
        load_catalog(root / "manifest.yaml")


def test_coverage_type_targets_are_validated_against_cards(tmp_path: Path) -> None:
    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    counts = scheme["constraints"]["type_counts"][1]
    counts["principle"] -= 1
    counts["rule"] += 1
    _refresh_scheme_digest(scheme)
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="type counts do not match"):
        load_catalog(root / "manifest.yaml")


def test_coverage_introduction_order_enforces_the_answer_run_limit(
    tmp_path: Path,
) -> None:
    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    scheme["constraints"]["max_same_answer_run"] = 2
    _refresh_scheme_digest(scheme)
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="exceeds max_same_answer_run"):
        load_catalog(root / "manifest.yaml")


def test_foundation_requires_one_representative_per_published_subtopic(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    current = catalog.coverage.schemes[catalog.coverage.current]
    dependents = {
        prerequisite
        for item in catalog.principles
        if item.id in current.assignments
        for prerequisite in item.prerequisites
    }
    foundation, standard = next(
        (foundation, standard)
        for foundation in catalog.principles
        for standard in catalog.principles
        if foundation.id in current.assignments
        and standard.id in current.assignments
        and current.assignments[foundation.id].tier == 1
        and current.assignments[standard.id].tier == 2
        and foundation.type == standard.type
        and foundation.question is not None
        and standard.question is not None
        and foundation.question.correct == standard.question.correct
        and catalog.taxonomy.assignments[foundation.id]
        != catalog.taxonomy.assignments[standard.id]
        and not foundation.prerequisites
        and not standard.prerequisites
        and foundation.id not in dependents
        and standard.id not in dependents
    )

    root = _copy_catalog(tmp_path)
    path = root / "coverage-tiers.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    scheme = document["schemes"][document["current"]]
    assignments = scheme["assignments"]
    assignments[foundation.id]["tier"], assignments[standard.id]["tier"] = (
        assignments[standard.id]["tier"],
        assignments[foundation.id]["tier"],
    )
    assignments[foundation.id]["introduction_order"], assignments[standard.id][
        "introduction_order"
    ] = (
        assignments[standard.id]["introduction_order"],
        assignments[foundation.id]["introduction_order"],
    )
    _refresh_scheme_digest(scheme)
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="foundation tier must cover"):
        load_catalog(root / "manifest.yaml")


def test_new_candidates_unlock_tiers_from_initial_introduction_only() -> None:
    catalog = load_catalog()
    introduced = coverage_introduction_order(catalog)
    state = {
        "items": [
            {"id": item.id, "status": "not_started"}
            for item in introduced
        ]
        + [{"id": "ANOTHER-CATALOG-ITEM", "status": "not_started"}]
    }

    assert unlocked_coverage_tier(catalog, state) == 1
    assert new_study_candidates(catalog, state) == tuple(
        item
        for item in introduced
        if coverage_assignment(catalog, item).tier == 1
    )

    for record in state["items"]:
        if record["id"].startswith("S-K6-") and coverage_assignment(
            catalog, record["id"]
        ).tier == 1:
            record["status"] = "review_due"

    assert unlocked_coverage_tier(catalog, state) == 2
    expected = tuple(
        item
        for item in introduced
        if coverage_assignment(catalog, item).tier == 2
    )
    assert new_study_candidates(catalog, state) == expected

    for record in state["items"]:
        if record["id"].startswith("S-K6-") and coverage_assignment(
            catalog, record["id"]
        ).tier == 2:
            record["status"] = "retained_14d"

    assert unlocked_coverage_tier(catalog, state) == 3


def test_missing_study_records_remain_not_started_and_explicit_ceiling_is_pure() -> None:
    catalog = load_catalog()
    state = {"items": []}

    before = repr(state)
    candidates = new_study_candidates(catalog, state, ceiling=2)

    assert candidates == coverage_introduction_order(catalog, ceiling=2)
    assert repr(state) == before
    assert unlocked_coverage_tier(catalog, state) == 1


def test_new_candidates_reject_duplicate_coverage_records() -> None:
    catalog = load_catalog()
    key = coverage_introduction_order(catalog, ceiling=1)[0].id
    state = {
        "items": [
            {"id": key, "status": "not_started"},
            {"id": key, "status": "review_due"},
        ]
    }

    with pytest.raises(ValueError, match="duplicate coverage item"):
        new_study_candidates(catalog, state)


def test_new_candidates_reject_unknown_coverage_statuses() -> None:
    catalog = load_catalog()
    foundation = coverage_introduction_order(catalog, ceiling=1)
    state = {
        "items": [
            {"id": item.id, "status": "not-strated"}
            for item in foundation
        ]
    }

    with pytest.raises(ValueError, match="unknown local study status"):
        unlocked_coverage_tier(catalog, state)


def test_new_candidates_do_not_return_or_reinterpret_review_queue_items() -> None:
    catalog = load_catalog()
    introduced = coverage_introduction_order(catalog, ceiling=1)
    urgent = introduced[0]
    state = {
        "items": [
            {"id": urgent.id, "status": "failed_retest_due"},
            {"id": "UNRELATED", "status": "not_started"},
        ]
    }

    candidates = new_study_candidates(catalog, state, ceiling=1)

    assert urgent not in candidates
    assert candidates == introduced[1:]
    assert state["items"][0]["status"] == "failed_retest_due"


def test_new_study_candidates_cli_lists_eligible_new_items_only(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text('{"items": []}\n', encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "principle_catalog",
            "new-study-candidates",
            "--state",
            str(state_path),
            "--ceiling",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    lines = completed.stdout.splitlines()
    assert lines[0].startswith("eligible new items only")
    assert len(lines[1:]) == 32
    assert state_path.read_text(encoding="utf-8") == '{"items": []}\n'


def test_coverage_history_allows_only_append_only_new_versions(tmp_path: Path) -> None:
    previous = tmp_path / "previous.yaml"
    current = tmp_path / "current.yaml"
    original = yaml.safe_load(COVERAGE_TIERS_PATH.read_text(encoding="utf-8"))
    _write_yaml(previous, original)

    appended = deepcopy(original)
    old_id = appended["current"]
    appended["schemes"][old_id]["status"] = "archived"
    new_id = "steel-coverage-v2"
    appended["schemes"][new_id] = deepcopy(appended["schemes"][old_id])
    appended["schemes"][new_id]["status"] = "current"
    appended["current"] = new_id
    _write_yaml(current, appended)

    validate_coverage_tier_history(previous, current)

    del appended["schemes"][old_id]
    _write_yaml(current, appended)
    with pytest.raises(
        ValueError,
        match=f"past coverage scheme {old_id} must not change or be removed",
    ):
        validate_coverage_tier_history(previous, current)


def test_coverage_history_rejects_rewriting_an_existing_scheme(
    tmp_path: Path,
) -> None:
    previous = tmp_path / "previous.yaml"
    current = tmp_path / "current.yaml"
    document = yaml.safe_load(COVERAGE_TIERS_PATH.read_text(encoding="utf-8"))
    _write_yaml(previous, document)
    scheme_id = document["current"]
    scheme = document["schemes"][scheme_id]
    assignment = next(iter(scheme["assignments"].values()))
    replacement = next(
        reason
        for reason in (
            "coverage_representative",
            "prerequisite",
            "standard_application",
            "basic_identification",
            "exception_detail",
            "integrated_judgment",
        )
        if reason not in assignment["reasons"]
    )
    assignment["reasons"].append(replacement)
    _refresh_scheme_digest(scheme)
    _write_yaml(current, document)

    with pytest.raises(
        ValueError,
        match=f"past coverage scheme {scheme_id} must not change or be removed",
    ):
        validate_coverage_tier_history(previous, current)


def test_current_coverage_scheme_must_be_the_highest_version(
    tmp_path: Path,
) -> None:
    previous = tmp_path / "previous.yaml"
    current = tmp_path / "current.yaml"
    document = yaml.safe_load(COVERAGE_TIERS_PATH.read_text(encoding="utf-8"))
    _write_yaml(previous, document)
    old_id = document["current"]
    newer = deepcopy(document["schemes"][old_id])
    newer["status"] = "archived"
    document["schemes"]["steel-coverage-v2"] = newer
    _write_yaml(current, document)

    with pytest.raises(ValueError, match="must have the highest version"):
        validate_coverage_tier_history(previous, current)


def test_verify_coverage_tiers_cli_accepts_unchanged_registry() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "principle_catalog",
            "verify-coverage-tiers",
            "--previous",
            str(COVERAGE_TIERS_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "valid coverage tiers" in completed.stdout
