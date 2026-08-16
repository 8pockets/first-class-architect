from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from principle_catalog.catalog import load_catalog
from principle_catalog import __main__ as cli
from principle_catalog.models import CoverageAssignment
from principle_catalog.research_questions import (
    RESEARCH_COVERAGE_TIERS_PATH,
    RESEARCH_QUESTIONS_PATH,
    load_research_coverage,
    load_research_questions,
    research_coverage_release_sha256,
    research_question_release_sha256,
    validate_research_coverage_history,
    validate_research_question_history,
)


PUBLISHED = "S-K6-FRAME-H-SECTION-AXIS-ROLE"
PRINCIPLE = "S-K6-H-SECTION-FLANGE-BENDING"
IDENTIFICATION = "S-K6-COLUMN-BASE-TYPES-FIXITY-ORDER"
RULE = "S-K6-COLUMN-BASE-NOTIFICATION-1456"
RESEARCH_KEYS = (PRINCIPLE, IDENTIFICATION, RULE)


def _write_yaml(path: Path, document: object) -> None:
    path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _tiny_catalog():
    catalog = load_catalog()
    selected = {PUBLISHED, *RESEARCH_KEYS}
    principles = tuple(item for item in catalog.principles if item.id in selected)
    assignments = {
        key: subtopic
        for key, subtopic in catalog.taxonomy.assignments.items()
        if key in selected
    }
    selected_subtopics = set(assignments.values())
    groups = tuple(
        replace(
            group,
            subtopics=tuple(
                subtopic
                for subtopic in group.subtopics
                if subtopic.id in selected_subtopics
            ),
        )
        for group in catalog.taxonomy.groups
        if any(subtopic.id in selected_subtopics for subtopic in group.subtopics)
    )
    taxonomy = replace(catalog.taxonomy, groups=groups, assignments=assignments)
    identities = replace(
        catalog.identities,
        active={key: value for key, value in catalog.identities.active.items() if key in selected},
        retired={},
    )
    current_id = catalog.coverage.current
    current = replace(
        catalog.coverage.schemes[current_id],
        assignments={
            PUBLISHED: CoverageAssignment(
                tier=1,
                introduction_order=1,
                reasons=("coverage_representative",),
            )
        },
    )
    coverage = replace(
        catalog.coverage,
        schemes={current_id: current},
    )
    return replace(
        catalog,
        principles=principles,
        taxonomy=taxonomy,
        identities=identities,
        coverage=coverage,
    )


def _release_digest(
    release_id: str,
    *,
    row_name: str,
    items: dict[str, object],
    revisions: dict[str, int],
    active: list[str],
) -> str:
    rows: list[dict[str, object]] = []
    for key in sorted(revisions):
        record = items[key]
        for revision in record["revision_history"][: revisions[key]]:
            row = {
                "key": key,
                "code": record["code"],
                **revision,
            }
            if row_name == "questions":
                row["type"] = record["type"]
            rows.append(row)
    canonical = json.dumps(
        {"id": release_id, "active": sorted(active), row_name: rows},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _refresh_releases(document: dict[str, object], row_name: str) -> None:
    items = document["items"]
    for release in document["releases"]:
        release["content_sha256"] = _release_digest(
            release["id"],
            row_name=row_name,
            items=items,
            revisions=release["revisions"],
            active=release["active"],
        )


def _question_document(catalog) -> dict[str, object]:
    by_id = {item.id: item for item in catalog.principles}
    items = {
        PRINCIPLE: {
            "code": by_id[PRINCIPLE].code,
            "type": by_id[PRINCIPLE].type,
            "revision_history": [
                {
                    "revision": 1,
                    "state": "provisional_answer",
                    "prompt": "H形鋼フランジの役割について、正しい結論はどちらか。",
                    "choices": {
                        "A": "曲げに伴う軸方向力を負担する",
                        "B": "主としてせん断力を負担する",
                    },
                    "answer": "A",
                    "details": {
                        "conclusion": "フランジは曲げに伴う軸方向力を負担する。",
                        "reason": "曲げ応力は断面外縁ほど大きくなるため。",
                        "conditions": ["曲げを受けるH形鋼"],
                    },
                    "evidence": [
                        {
                            "kind": "ledger",
                            "locator": "教材P176",
                            "supports": ["answer", "details"],
                        },
                    ],
                }
            ],
        },
        IDENTIFICATION: {
            "code": by_id[IDENTIFICATION].code,
            "type": by_id[IDENTIFICATION].type,
            "revision_history": [
                {
                    "revision": 1,
                    "state": "provisional_answer",
                    "prompt": "柱脚形式の固定度について、正しい結論はどちらか。",
                    "choices": {
                        "A": "埋込み形式は露出形式より固定度が高い",
                        "B": "露出形式は埋込み形式より固定度が高い",
                    },
                    "answer": "A",
                    "details": {
                        "definition": "柱脚は埋込み・根巻き・露出形式に分ける。",
                        "distinguishing_conditions": ["基礎との接合形式で識別する"],
                        "confusable_points": ["固定度の順序と耐力を混同しない"],
                    },
                    "evidence": [
                        {
                            "kind": "external",
                            "source_class": "official",
                            "title": "柱脚設計資料",
                            "locator": "2.1 柱脚形式",
                            "url": "https://example.com/column-base",
                            "supports": ["answer", "details"],
                        }
                    ],
                }
            ],
        },
        RULE: {
            "code": by_id[RULE].code,
            "type": by_id[RULE].type,
            "revision_history": [
                {
                    "revision": 1,
                    "state": "pending",
                    "prompt": "柱脚の仕様規定について、正しい結論はどちらか。",
                    "choices": {
                        "A": "指定告示の仕様規定を確認する",
                        "B": "告示に関係なく同じ仕様を用いる",
                    },
                    "answer": None,
                    "details": {
                        "rule": "適用する告示と仕様規定を対応させる。",
                        "applicability": ["鉄骨造柱脚の仕様を確認する場合"],
                        "numbers_exceptions": [],
                    },
                    "evidence": [
                        {
                            "kind": "ledger",
                            "locator": "教材P204",
                            "supports": ["details"],
                        },
                        {
                            "kind": "codex",
                            "supplement": "告示番号と現行規定の対応は継続確認する。",
                            "supports": ["details"],
                        },
                    ],
                }
            ],
        },
    }
    release_id = "steel-research-questions-v1"
    document: dict[str, object] = {
        "version": 1,
        "releases": [
            {
                "id": release_id,
                "active": sorted(RESEARCH_KEYS),
                "revisions": {key: 1 for key in RESEARCH_KEYS},
                "content_sha256": "",
            }
        ],
        "items": items,
    }
    _refresh_releases(document, "questions")
    return document


def _coverage_document(catalog) -> dict[str, object]:
    by_id = {item.id: item for item in catalog.principles}
    items = {
        PRINCIPLE: {
            "code": by_id[PRINCIPLE].code,
            "revision_history": [
                {
                    "revision": 1,
                    "tier": 2,
                    "reasons": ["standard_application"],
                }
            ],
        },
        IDENTIFICATION: {
            "code": by_id[IDENTIFICATION].code,
            "revision_history": [
                {
                    "revision": 1,
                    "tier": 1,
                    "reasons": [
                        "coverage_representative",
                        "prerequisite",
                        "basic_identification",
                    ],
                }
            ],
        },
        RULE: {
            "code": by_id[RULE].code,
            "revision_history": [
                {
                    "revision": 1,
                    "tier": 3,
                    "reasons": ["exception_detail"],
                }
            ],
        },
    }
    release_id = "steel-research-coverage-v1"
    document: dict[str, object] = {
        "version": 1,
        "releases": [
            {
                "id": release_id,
                "active": sorted(RESEARCH_KEYS),
                "revisions": {key: 1 for key in RESEARCH_KEYS},
                "content_sha256": "",
            }
        ],
        "items": items,
    }
    _refresh_releases(document, "assignments")
    return document


def test_versioned_research_ledgers_load_a_complete_tiny_catalog(tmp_path: Path) -> None:
    catalog = _tiny_catalog()
    questions_path = tmp_path / "research-questions.yaml"
    coverage_path = tmp_path / "research-coverage-tiers.yaml"
    _write_yaml(questions_path, _question_document(catalog))
    questions = load_research_questions(catalog, questions_path)
    _write_yaml(coverage_path, _coverage_document(catalog))
    coverage = load_research_coverage(catalog, questions, coverage_path)

    assert RESEARCH_QUESTIONS_PATH.name == "research-questions.yaml"
    assert RESEARCH_COVERAGE_TIERS_PATH.name == "research-coverage-tiers.yaml"
    assert set(questions.items) == set(coverage.items) == set(RESEARCH_KEYS)
    assert set(questions.active_keys) == set(coverage.active_keys) == set(RESEARCH_KEYS)
    assert questions.items[PRINCIPLE].current.answer == "A"
    assert questions.items[RULE].current.answer is None
    assert questions.items[RULE].current.state == "pending"
    assert coverage.items[IDENTIFICATION].current.tier == 1
    assert coverage.items[RULE].current.tier == 3


def test_public_release_digest_helpers_accept_raw_production_documents() -> None:
    catalog = _tiny_catalog()
    questions = _question_document(catalog)
    question_release = questions["releases"][0]
    assert research_question_release_sha256(
        question_release["id"],
        questions["items"],
        question_release["revisions"],
        question_release["active"],
    ) == question_release["content_sha256"]

    coverage = _coverage_document(catalog)
    coverage_release = coverage["releases"][0]
    assert research_coverage_release_sha256(
        coverage_release["id"],
        coverage["items"],
        coverage_release["revisions"],
        coverage_release["active"],
    ) == coverage_release["content_sha256"]


def test_research_questions_require_every_active_unconfirmed_item_once(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    document = _question_document(catalog)
    del document["items"][RULE]
    del document["releases"][0]["revisions"][RULE]
    _refresh_releases(document, "questions")
    path = tmp_path / "missing.yaml"
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="active non-source_checked items exactly once"):
        load_research_questions(catalog, path)


def test_research_question_code_is_immutable_catalog_identity(tmp_path: Path) -> None:
    catalog = _tiny_catalog()
    document = _question_document(catalog)
    document["items"][PRINCIPLE]["code"] = "structure.steel.changed"
    _refresh_releases(document, "questions")
    path = tmp_path / "changed-code.yaml"
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="published code must remain"):
        load_research_questions(catalog, path)


@pytest.mark.parametrize(
    ("state", "answer"),
    (("pending", "A"), ("provisional_answer", None)),
)
def test_research_question_state_and_answer_must_agree(
    tmp_path: Path,
    state: str,
    answer: str | None,
) -> None:
    catalog = _tiny_catalog()
    document = _question_document(catalog)
    revision = document["items"][PRINCIPLE]["revision_history"][0]
    revision["state"] = state
    revision["answer"] = answer
    _refresh_releases(document, "questions")
    path = tmp_path / "state.yaml"
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="answer must be"):
        load_research_questions(catalog, path)


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (
            lambda revision: revision["choices"].__setitem__(
                "A", revision["choices"]["B"]
            ),
            "choices must be distinct",
        ),
        (
            lambda revision: revision["choices"].__setitem__("A", "絶対に正しい"),
            "forbidden cue",
        ),
        (
            lambda revision: revision["choices"].__setitem__("A", "あ" * 41),
            "40 characters",
        ),
        (
            lambda revision: revision["choices"].__setitem__("A", "短い"),
            "similar in length",
        ),
        (
            lambda revision: revision.__setitem__("prompt", "理由を二つ述べなさい。"),
            "single-axis binary form",
        ),
    ),
)
def test_research_question_quality_constraints(
    tmp_path: Path,
    mutate,
    message: str,
) -> None:
    catalog = _tiny_catalog()
    document = _question_document(catalog)
    mutate(document["items"][PRINCIPLE]["revision_history"][0])
    _refresh_releases(document, "questions")
    path = tmp_path / "quality.yaml"
    _write_yaml(path, document)

    with pytest.raises(ValueError, match=message):
        load_research_questions(catalog, path)


def test_type_specific_details_must_match_the_catalog_type(tmp_path: Path) -> None:
    catalog = _tiny_catalog()
    document = _question_document(catalog)
    document["items"][RULE]["revision_history"][0]["details"] = {
        "conclusion": "誤った形",
        "reason": "誤った形",
        "conditions": ["誤った形"],
    }
    _refresh_releases(document, "questions")
    path = tmp_path / "details.yaml"
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="rule details keys"):
        load_research_questions(catalog, path)


@pytest.mark.parametrize(
    ("evidence", "message"),
    (
        (
            [
                {
                    "kind": "external",
                    "source_class": "official",
                    "title": "source",
                    "locator": "section",
                    "supports": ["answer"],
                }
            ],
            "external evidence keys",
        ),
        (
            [
                {
                    "kind": "codex",
                    "supplement": "only",
                    "supports": ["answer"],
                }
            ],
            "codex evidence cannot support answer",
        ),
        (
            [
                {
                    "kind": "external",
                    "source_class": "official",
                    "title": "source",
                    "locator": "section",
                    "url": "http://example.com/source",
                    "supports": ["answer"],
                }
            ],
            "absolute HTTPS",
        ),
    ),
)
def test_evidence_records_have_kind_specific_provenance(
    tmp_path: Path,
    evidence: list[dict[str, str]],
    message: str,
) -> None:
    catalog = _tiny_catalog()
    document = _question_document(catalog)
    document["items"][PRINCIPLE]["revision_history"][0]["evidence"] = evidence
    _refresh_releases(document, "questions")
    path = tmp_path / "evidence.yaml"
    _write_yaml(path, document)

    with pytest.raises(ValueError, match=message):
        load_research_questions(catalog, path)


def test_provisional_answer_requires_ledger_official_or_two_independent_explanations(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    document = _question_document(catalog)
    revision = document["items"][PRINCIPLE]["revision_history"][0]
    revision["evidence"] = [
        {
            "kind": "external",
            "source_class": "explanation",
            "title": "解説A",
            "locator": "H形鋼の役割",
            "url": "https://one.example/steel",
            "supports": ["answer", "details"],
        }
    ]
    _refresh_releases(document, "questions")
    path = tmp_path / "one-explanation.yaml"
    _write_yaml(path, document)
    with pytest.raises(ValueError, match="provisional answer requires"):
        load_research_questions(catalog, path)

    revision["evidence"].append(
        {
            "kind": "external",
            "source_class": "explanation",
            "title": "解説B",
            "locator": "フランジとウェブ",
            "url": "https://two.example/h-section",
            "supports": ["answer"],
        }
    )
    _refresh_releases(document, "questions")
    _write_yaml(path, document)
    loaded = load_research_questions(catalog, path)
    assert loaded.items[PRINCIPLE].current.answer == "A"


def test_pending_question_allows_codex_question_and_details_support(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    document = _question_document(catalog)
    revision = document["items"][PRINCIPLE]["revision_history"][0]
    revision["state"] = "pending"
    revision["answer"] = None
    revision["evidence"] = [
        {
            "kind": "codex",
            "supplement": "推論補足だけなので正答は保留する。",
            "supports": ["question", "details"],
        }
    ]
    _refresh_releases(document, "questions")
    path = tmp_path / "codex-pending.yaml"
    _write_yaml(path, document)

    loaded = load_research_questions(catalog, path)
    assert loaded.items[PRINCIPLE].current.state == "pending"
    assert loaded.items[PRINCIPLE].current.evidence[0].supports == (
        "question",
        "details",
    )


def test_question_revisions_are_contiguous_released_and_digest_bound(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    document = _question_document(catalog)
    second = deepcopy(document["items"][PRINCIPLE]["revision_history"][0])
    second["revision"] = 3
    document["items"][PRINCIPLE]["revision_history"].append(second)
    document["releases"][0]["revisions"][PRINCIPLE] = 2
    _refresh_releases(document, "questions")
    path = tmp_path / "revision.yaml"
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="revision must be 2"):
        load_research_questions(catalog, path)

    document = _question_document(catalog)
    document["releases"][0]["content_sha256"] = "0" * 64
    _write_yaml(path, document)
    with pytest.raises(ValueError, match="differs from its audited snapshot"):
        load_research_questions(catalog, path)


def test_question_history_accepts_append_and_rejects_rewrite(tmp_path: Path) -> None:
    catalog = _tiny_catalog()
    previous = _question_document(catalog)
    current = deepcopy(previous)
    second = deepcopy(current["items"][PRINCIPLE]["revision_history"][0])
    second["revision"] = 2
    second["details"]["reason"] = "断面外縁の曲げ応力を担うため。"
    current["items"][PRINCIPLE]["revision_history"].append(second)
    current["releases"].append(
        {
            "id": "steel-research-questions-v2",
            "active": sorted(RESEARCH_KEYS),
            "revisions": {
                **current["releases"][0]["revisions"],
                PRINCIPLE: 2,
            },
            "content_sha256": "",
        }
    )
    _refresh_releases(current, "questions")
    previous_path = tmp_path / "previous.yaml"
    current_path = tmp_path / "current.yaml"
    _write_yaml(previous_path, previous)
    _write_yaml(current_path, current)

    validate_research_question_history(catalog, previous_path, current_path)

    rewritten = deepcopy(current)
    rewritten["items"][PRINCIPLE]["revision_history"][0]["details"][
        "reason"
    ] = "過去を書き換えた。"
    _refresh_releases(rewritten, "questions")
    _write_yaml(current_path, rewritten)
    with pytest.raises(ValueError, match="past question revision"):
        validate_research_question_history(catalog, previous_path, current_path)


def _loaded_questions(catalog, tmp_path: Path):
    path = tmp_path / "questions.yaml"
    _write_yaml(path, _question_document(catalog))
    return load_research_questions(catalog, path)


def test_candidate_coverage_assigns_every_question_and_global_foundation(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    questions = _loaded_questions(catalog, tmp_path)
    path = tmp_path / "coverage.yaml"
    _write_yaml(path, _coverage_document(catalog))
    coverage = load_research_coverage(catalog, questions, path)

    assert {item.current.tier for item in coverage.items.values()} == {1, 2, 3}
    assert sum(item.current.tier == 1 for item in coverage.items.values()) == 1


def test_candidate_coverage_rejects_missing_items_and_unknown_reasons(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    questions = _loaded_questions(catalog, tmp_path)
    document = _coverage_document(catalog)
    del document["items"][RULE]
    del document["releases"][0]["revisions"][RULE]
    _refresh_releases(document, "assignments")
    path = tmp_path / "coverage.yaml"
    _write_yaml(path, document)
    with pytest.raises(ValueError, match="every research question exactly once"):
        load_research_coverage(catalog, questions, path)

    document = _coverage_document(catalog)
    document["items"][PRINCIPLE]["revision_history"][0]["reasons"] = [
        "personal_difficulty"
    ]
    _refresh_releases(document, "assignments")
    _write_yaml(path, document)
    with pytest.raises(ValueError, match="reasons are invalid"):
        load_research_coverage(catalog, questions, path)


def test_candidate_foundation_is_exactly_one_per_global_subtopic(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    questions = _loaded_questions(catalog, tmp_path)
    document = _coverage_document(catalog)
    document["items"][PRINCIPLE]["revision_history"][0] = {
        "revision": 1,
        "tier": 1,
        "reasons": ["coverage_representative"],
    }
    _refresh_releases(document, "assignments")
    path = tmp_path / "coverage.yaml"
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="global foundation must cover every subtopic exactly once"):
        load_research_coverage(catalog, questions, path)


def test_candidate_prerequisite_cannot_be_in_a_later_tier(tmp_path: Path) -> None:
    catalog = _tiny_catalog()
    questions = _loaded_questions(catalog, tmp_path)
    document = _coverage_document(catalog)
    document["items"][IDENTIFICATION]["revision_history"][0] = {
        "revision": 1,
        "tier": 3,
        "reasons": ["integrated_judgment", "prerequisite"],
    }
    document["items"][RULE]["revision_history"][0] = {
        "revision": 1,
        "tier": 2,
        "reasons": ["standard_application"],
    }
    _refresh_releases(document, "assignments")
    path = tmp_path / "coverage.yaml"
    _write_yaml(path, document)

    with pytest.raises(ValueError, match="prerequisite in a later candidate tier"):
        load_research_coverage(catalog, questions, path)


def test_candidate_coverage_history_accepts_append_and_rejects_rewrite(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    questions = _loaded_questions(catalog, tmp_path)
    previous = _coverage_document(catalog)
    current = deepcopy(previous)
    second = deepcopy(current["items"][RULE]["revision_history"][0])
    second["revision"] = 2
    second["reasons"] = ["integrated_judgment"]
    current["items"][RULE]["revision_history"].append(second)
    current["releases"].append(
        {
            "id": "steel-research-coverage-v2",
            "active": sorted(RESEARCH_KEYS),
            "revisions": {
                **current["releases"][0]["revisions"],
                RULE: 2,
            },
            "content_sha256": "",
        }
    )
    _refresh_releases(current, "assignments")
    previous_path = tmp_path / "previous-coverage.yaml"
    current_path = tmp_path / "current-coverage.yaml"
    _write_yaml(previous_path, previous)
    _write_yaml(current_path, current)

    validate_research_coverage_history(
        catalog,
        questions,
        previous_path,
        current_path,
    )

    rewritten = deepcopy(current)
    rewritten["items"][RULE]["revision_history"][0]["reasons"] = [
        "exception_detail",
        "prerequisite",
    ]
    _refresh_releases(rewritten, "assignments")
    _write_yaml(current_path, rewritten)
    with pytest.raises(ValueError, match="past coverage revision"):
        validate_research_coverage_history(
            catalog,
            questions,
            previous_path,
            current_path,
        )


def test_promoted_items_leave_active_but_keep_append_only_history(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    promoted_principles = tuple(
        replace(item, editorial_status="source_checked")
        if item.id == PRINCIPLE
        else item
        for item in catalog.principles
    )
    current_id = catalog.coverage.current
    formal_scheme = catalog.coverage.schemes[current_id]
    promoted_scheme = replace(
        formal_scheme,
        assignments={
            **formal_scheme.assignments,
            PRINCIPLE: CoverageAssignment(
                tier=2,
                introduction_order=2,
                reasons=("standard_application",),
            ),
        },
    )
    promoted_catalog = replace(
        catalog,
        principles=promoted_principles,
        coverage=replace(
            catalog.coverage,
            schemes={current_id: promoted_scheme},
        ),
    )

    previous_questions = _question_document(catalog)
    current_questions = deepcopy(previous_questions)
    current_questions["releases"].append(
        {
            "id": "steel-research-questions-v2",
            "active": sorted({IDENTIFICATION, RULE}),
            "revisions": deepcopy(current_questions["releases"][0]["revisions"]),
            "content_sha256": "",
        }
    )
    _refresh_releases(current_questions, "questions")
    previous_questions_path = tmp_path / "previous-questions.yaml"
    current_questions_path = tmp_path / "current-questions.yaml"
    _write_yaml(previous_questions_path, previous_questions)
    _write_yaml(current_questions_path, current_questions)

    questions = load_research_questions(promoted_catalog, current_questions_path)
    assert PRINCIPLE in questions.items
    assert PRINCIPLE not in questions.active_keys
    validate_research_question_history(
        promoted_catalog,
        previous_questions_path,
        current_questions_path,
    )

    previous_coverage = _coverage_document(catalog)
    current_coverage = deepcopy(previous_coverage)
    current_coverage["releases"].append(
        {
            "id": "steel-research-coverage-v2",
            "active": sorted({IDENTIFICATION, RULE}),
            "revisions": deepcopy(current_coverage["releases"][0]["revisions"]),
            "content_sha256": "",
        }
    )
    _refresh_releases(current_coverage, "assignments")
    previous_coverage_path = tmp_path / "previous-coverage.yaml"
    current_coverage_path = tmp_path / "current-coverage.yaml"
    _write_yaml(previous_coverage_path, previous_coverage)
    _write_yaml(current_coverage_path, current_coverage)

    coverage = load_research_coverage(
        promoted_catalog,
        questions,
        current_coverage_path,
    )
    assert PRINCIPLE in coverage.items
    assert PRINCIPLE not in coverage.active_keys
    validate_research_coverage_history(
        promoted_catalog,
        questions,
        previous_coverage_path,
        current_coverage_path,
    )


def test_retired_items_leave_active_but_keep_typed_append_only_history(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    retired_identity = catalog.identities.active[PRINCIPLE]
    retired_catalog = replace(
        catalog,
        principles=tuple(item for item in catalog.principles if item.id != PRINCIPLE),
        identities=replace(
            catalog.identities,
            active={
                key: identity
                for key, identity in catalog.identities.active.items()
                if key != PRINCIPLE
            },
            retired={PRINCIPLE: retired_identity},
        ),
        taxonomy=replace(
            catalog.taxonomy,
            assignments={
                key: subtopic
                for key, subtopic in catalog.taxonomy.assignments.items()
                if key != PRINCIPLE
            },
        ),
    )

    previous_questions = _question_document(catalog)
    current_questions = deepcopy(previous_questions)
    current_questions["releases"].append(
        {
            "id": "steel-research-questions-v2",
            "active": sorted({IDENTIFICATION, RULE}),
            "revisions": deepcopy(current_questions["releases"][0]["revisions"]),
            "content_sha256": "",
        }
    )
    _refresh_releases(current_questions, "questions")
    previous_questions_path = tmp_path / "retired-previous-questions.yaml"
    current_questions_path = tmp_path / "retired-current-questions.yaml"
    _write_yaml(previous_questions_path, previous_questions)
    _write_yaml(current_questions_path, current_questions)

    questions = load_research_questions(retired_catalog, current_questions_path)
    assert questions.items[PRINCIPLE].type == "principle"
    assert PRINCIPLE not in questions.active_keys
    validate_research_question_history(
        retired_catalog,
        previous_questions_path,
        current_questions_path,
    )

    previous_coverage = _coverage_document(catalog)
    current_coverage = deepcopy(previous_coverage)
    current_coverage["releases"].append(
        {
            "id": "steel-research-coverage-v2",
            "active": sorted({IDENTIFICATION, RULE}),
            "revisions": deepcopy(current_coverage["releases"][0]["revisions"]),
            "content_sha256": "",
        }
    )
    _refresh_releases(current_coverage, "assignments")
    previous_coverage_path = tmp_path / "retired-previous-coverage.yaml"
    current_coverage_path = tmp_path / "retired-current-coverage.yaml"
    _write_yaml(previous_coverage_path, previous_coverage)
    _write_yaml(current_coverage_path, current_coverage)

    coverage = load_research_coverage(
        retired_catalog,
        questions,
        current_coverage_path,
    )
    assert PRINCIPLE in coverage.items
    assert PRINCIPLE not in coverage.active_keys
    validate_research_coverage_history(
        retired_catalog,
        questions,
        previous_coverage_path,
        current_coverage_path,
    )


def test_history_allows_a_new_active_item_only_in_an_appended_release(
    tmp_path: Path,
) -> None:
    catalog = _tiny_catalog()
    complete_questions = _question_document(catalog)
    previous_questions = deepcopy(complete_questions)
    del previous_questions["items"][RULE]
    previous_questions["releases"][0]["active"].remove(RULE)
    del previous_questions["releases"][0]["revisions"][RULE]
    _refresh_releases(previous_questions, "questions")
    current_questions = deepcopy(previous_questions)
    current_questions["items"][RULE] = deepcopy(complete_questions["items"][RULE])
    current_questions["releases"].append(
        {
            "id": "steel-research-questions-v2",
            "active": sorted(RESEARCH_KEYS),
            "revisions": {key: 1 for key in RESEARCH_KEYS},
            "content_sha256": "",
        }
    )
    _refresh_releases(current_questions, "questions")
    previous_questions_path = tmp_path / "new-previous-questions.yaml"
    current_questions_path = tmp_path / "new-current-questions.yaml"
    _write_yaml(previous_questions_path, previous_questions)
    _write_yaml(current_questions_path, current_questions)

    questions = load_research_questions(catalog, current_questions_path)
    validate_research_question_history(
        catalog,
        previous_questions_path,
        current_questions_path,
    )

    complete_coverage = _coverage_document(catalog)
    previous_coverage = deepcopy(complete_coverage)
    del previous_coverage["items"][RULE]
    previous_coverage["releases"][0]["active"].remove(RULE)
    del previous_coverage["releases"][0]["revisions"][RULE]
    _refresh_releases(previous_coverage, "assignments")
    current_coverage = deepcopy(previous_coverage)
    current_coverage["items"][RULE] = deepcopy(complete_coverage["items"][RULE])
    current_coverage["releases"].append(
        {
            "id": "steel-research-coverage-v2",
            "active": sorted(RESEARCH_KEYS),
            "revisions": {key: 1 for key in RESEARCH_KEYS},
            "content_sha256": "",
        }
    )
    _refresh_releases(current_coverage, "assignments")
    previous_coverage_path = tmp_path / "new-previous-coverage.yaml"
    current_coverage_path = tmp_path / "new-current-coverage.yaml"
    _write_yaml(previous_coverage_path, previous_coverage)
    _write_yaml(current_coverage_path, current_coverage)

    validate_research_coverage_history(
        catalog,
        questions,
        previous_coverage_path,
        current_coverage_path,
    )


def test_production_research_ledgers_keep_the_approved_v1_snapshot() -> None:
    catalog = load_catalog()
    questions = load_research_questions(catalog)
    coverage = load_research_coverage(catalog, questions)
    active = questions.active_keys

    assert len(active) == 100
    assert coverage.active_keys == active
    assert Counter(questions.items[key].type for key in active) == {
        "principle": 14,
        "rule": 55,
        "identification": 31,
    }
    assert Counter(questions.items[key].current.state for key in active) == {
        "provisional_answer": 99,
        "pending": 1,
    }
    assert Counter(questions.items[key].current.answer for key in active) == {
        "A": 49,
        "B": 50,
        None: 1,
    }
    assert Counter(coverage.items[key].current.tier for key in active) == {
        1: 5,
        2: 47,
        3: 48,
    }

    question_release = questions.releases[-1]
    coverage_release = coverage.releases[-1]
    assert (question_release.id, question_release.content_sha256) == (
        "steel-research-questions-v1",
        "79fa55b2e60cfb3f5021533e0d2573eb459fc6832221ef0123f56ddd7455a549",
    )
    assert (coverage_release.id, coverage_release.content_sha256) == (
        "steel-research-coverage-v1",
        "034e3e0097bab2f7634708269b993966121ec24ee71ead7039f00fcec0178b7a",
    )

    pending = {
        key for key in active if questions.items[key].current.state == "pending"
    }
    assert pending == {"S-K6-STEEL-END-TAB-RETENTION-CONDITIONS"}
    narrowing_phrase = "確認した外部資料の支持範囲へ設問と暫定内容を狭めた"
    narrowing = {
        key
        for key in active
        for evidence in questions.items[key].current.evidence
        if evidence.kind == "codex"
        and evidence.supplement is not None
        and narrowing_phrase in evidence.supplement
    }
    assert narrowing == {
        "S-K6-BRACED-FRAME-COLUMN-BRACE-CAPACITY-SUM",
        "S-K6-FIREPROOFING-REQUIRED-ABOVE-250C",
        "S-K6-OVERHEAD-CRANE-SEISMIC-WEIGHT",
        "S-K6-STEEL-FIRE-STRENGTH-FIREPROOFING",
    }
    externally_checked = {
        key
        for key in active
        if any(
            evidence.kind == "external"
            for evidence in questions.items[key].current.evidence
        )
    }
    assert externally_checked == narrowing | {
        "S-K6-WELD-BEAD-DEFINITION",
        "S-K6-WELD-NO-CONSTRUCTION-NOISE",
    }
    bead = questions.items["S-K6-WELD-BEAD-DEFINITION"].current
    noise = questions.items["S-K6-WELD-NO-CONSTRUCTION-NOISE"].current
    assert bead.answer == "A" and "1回のパス" in bead.choice_a
    assert noise.answer == "B" and "騒音が生じる" in noise.choice_b
    assert all(
        len(record.revision_history) == record.current.revision == 1
        for record in questions.items.values()
    )
    assert all(
        len(record.revision_history) == record.current.revision == 1
        for record in coverage.items.values()
    )


def test_validate_cli_loads_both_fixed_research_ledgers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = _tiny_catalog()
    calls: list[tuple[str, object]] = []
    questions = SimpleNamespace(
        items={key: object() for key in RESEARCH_KEYS},
        active_keys=(IDENTIFICATION, RULE),
    )
    coverage = SimpleNamespace(
        items={
            PRINCIPLE: SimpleNamespace(current=SimpleNamespace(tier=2)),
            IDENTIFICATION: SimpleNamespace(current=SimpleNamespace(tier=1)),
            RULE: SimpleNamespace(current=SimpleNamespace(tier=3)),
        },
        active_keys=(IDENTIFICATION, RULE),
    )
    monkeypatch.setattr(cli, "load_catalog", lambda: catalog)
    monkeypatch.setattr(
        cli,
        "load_research_queries",
        lambda loaded: SimpleNamespace(items={}),
    )
    monkeypatch.setattr(
        cli,
        "load_research_questions",
        lambda loaded, path=RESEARCH_QUESTIONS_PATH: (
            calls.append(("questions", path)) or questions
        ),
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "load_research_coverage",
        lambda loaded, registered, path=RESEARCH_COVERAGE_TIERS_PATH: (
            calls.append(("coverage", (registered, path))) or coverage
        ),
        raising=False,
    )
    monkeypatch.setattr(cli, "load_public_progress", lambda: SimpleNamespace(items={}))
    monkeypatch.setattr(cli, "validate_public_progress", lambda loaded, progress: None)
    monkeypatch.setattr(sys, "argv", ["principle-catalog", "validate"])

    assert cli.main() == 0
    output = capsys.readouterr().out
    assert calls == [
        ("questions", RESEARCH_QUESTIONS_PATH),
        ("coverage", (questions, RESEARCH_COVERAGE_TIERS_PATH)),
    ]
    assert "research_questions=2" in output
    assert "research_tiers=1:1,2:0,3:1" in output


def test_verify_research_questions_cli_compares_previous_with_fixed_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = _tiny_catalog()
    previous = tmp_path / "previous-questions.yaml"
    calls: list[tuple[object, Path, Path]] = []
    monkeypatch.setattr(cli, "load_catalog", lambda: catalog)
    monkeypatch.setattr(
        cli,
        "validate_research_question_history",
        lambda loaded, previous_path, current_path: calls.append(
            (loaded, previous_path, current_path)
        ),
        raising=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "principle-catalog",
            "verify-research-questions",
            "--previous",
            str(previous),
        ],
    )

    assert cli.main() == 0
    assert calls == [(catalog, previous, RESEARCH_QUESTIONS_PATH)]
    assert (
        capsys.readouterr().out
        == f"valid research questions previous={previous}\n"
    )


def test_verify_research_coverage_cli_validates_paired_question_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = _tiny_catalog()
    previous_coverage = tmp_path / "previous-coverage.yaml"
    previous_questions = tmp_path / "previous-questions.yaml"
    current_questions = object()
    calls: list[tuple[str, tuple[object, ...]]] = []
    monkeypatch.setattr(cli, "load_catalog", lambda: catalog)
    monkeypatch.setattr(
        cli,
        "validate_research_question_history",
        lambda *args: calls.append(("questions", args)),
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "load_research_questions",
        lambda loaded: calls.append(("load-current-questions", (loaded,)))
        or current_questions,
    )
    monkeypatch.setattr(
        cli,
        "validate_research_coverage_history",
        lambda *args: calls.append(("coverage", args)),
        raising=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "principle-catalog",
            "verify-research-coverage",
            "--previous",
            str(previous_coverage),
            "--previous-questions",
            str(previous_questions),
        ],
    )

    assert cli.main() == 0
    assert calls == [
        (
            "questions",
            (catalog, previous_questions, RESEARCH_QUESTIONS_PATH),
        ),
        ("load-current-questions", (catalog,)),
        (
            "coverage",
            (
                catalog,
                current_questions,
                previous_coverage,
                RESEARCH_COVERAGE_TIERS_PATH,
            ),
        ),
    ]
    assert capsys.readouterr().out == (
        "valid research coverage "
        f"previous={previous_coverage} "
        f"previous_questions={previous_questions}\n"
    )
