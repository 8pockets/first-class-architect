"""Versioned provisional questions and candidate coverage for research cards.

These registries are deliberately separate from the issued question editions and
coverage schemes.  They can be reviewed and revised while an item remains
``source_gap`` or ``draft`` without weakening the publication contract of the
confirmed catalog.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, TypeVar, cast
from urllib.parse import urlparse

from principle_catalog.catalog import (
    CATALOG_ROOT,
    CatalogError,
    _exact_keys,
    _int,
    _list,
    _load_yaml,
    _mapping,
    _str,
)
from principle_catalog.models import (
    Catalog,
    ChoiceLabel,
    CoverageReason,
    CoverageTier,
    PrincipleType,
    ResearchCoverageRecord,
    ResearchCoverageRegistry,
    ResearchCoverageRelease,
    ResearchCoverageRevision,
    ResearchEvidence,
    ResearchEvidenceKind,
    ResearchEvidenceSupport,
    ResearchExternalSourceClass,
    ResearchIdentificationDetails,
    ResearchPrincipleDetails,
    ResearchQuestionDetails,
    ResearchQuestionRecord,
    ResearchQuestionRegistry,
    ResearchQuestionRelease,
    ResearchQuestionRevision,
    ResearchQuestionState,
    ResearchRuleDetails,
)


RESEARCH_QUESTIONS_PATH = CATALOG_ROOT / "research-questions.yaml"
RESEARCH_COVERAGE_TIERS_PATH = CATALOG_ROOT / "research-coverage-tiers.yaml"

_QUESTION_RELEASE_ID = re.compile(r"^steel-research-questions-v([1-9][0-9]*)$")
_COVERAGE_RELEASE_ID = re.compile(r"^steel-research-coverage-v([1-9][0-9]*)$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_QUESTION_ITEM_FIELDS = {"code", "type", "revision_history"}
_COVERAGE_ITEM_FIELDS = {"code", "revision_history"}
_QUESTION_REVISION_FIELDS = {
    "revision",
    "state",
    "prompt",
    "choices",
    "answer",
    "details",
    "evidence",
}
_COVERAGE_REVISION_FIELDS = {"revision", "tier", "reasons"}
_RELEASE_FIELDS = {"id", "active", "revisions", "content_sha256"}
_QUESTION_STATES = {"provisional_answer", "pending"}
_EVIDENCE_KINDS = {"ledger", "external", "codex"}
_EVIDENCE_SUPPORTS = {"question", "answer", "details"}
_EXTERNAL_SOURCE_CLASSES = {"official", "explanation"}
_COVERAGE_TIERS = {1, 2, 3}
_COVERAGE_REASONS = {
    "coverage_representative",
    "prerequisite",
    "standard_application",
    "basic_identification",
    "exception_detail",
    "integrated_judgment",
}
_QUESTION_SUFFIX = "正しい結論はどちらか。"
_PROMPT_FORBIDDEN = {
    "説明しなさい",
    "述べなさい",
    "誤っている",
    "正しくない",
}
_ANSWER_CUES = {"正解", "不正解", "誤答", "答え"}
_SYMBOL_CUES = {"(○)", "(×)", "[○]", "[×]", "【○】", "【×】"}
_CHOICE_CUES = {
    "必ず",
    "絶対",
    "両方",
    "双方",
    "いずれも",
    "どちらも",
    "どちらでもない",
}


def _contains_invisible(value: str) -> bool:
    return any(unicodedata.category(character) in {"Cc", "Cf"} for character in value)


def _normalized(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", value).casefold().strip(),
    )


def _string_list(value: object, path: Path, label: str) -> tuple[str, ...]:
    raw_values = _list(value, path, label)
    values = tuple(
        _str(raw, path, f"{label}[{index}]")
        for index, raw in enumerate(raw_values, start=1)
    )
    if len(values) != len(set(values)):
        raise CatalogError(f"{path}: {label} must not contain duplicates")
    return values


def _question_text(value: object, path: Path, label: str) -> str:
    text = _str(value, path, label)
    if value != text or "\n" in text or "\r" in text or _contains_invisible(text):
        raise CatalogError(f"{path}: {label} must be a trimmed visible single line")
    return text


def _question_details(
    value: object,
    item_type: PrincipleType,
    path: Path,
    label: str,
) -> ResearchQuestionDetails:
    details = _mapping(value, path, label)
    if item_type == "principle":
        expected = {"conclusion", "reason", "conditions"}
        if set(details) != expected:
            raise CatalogError(
                f"{path}: {label} principle details keys must be {sorted(expected)}"
            )
        conditions = _string_list(details["conditions"], path, f"{label}.conditions")
        if not conditions:
            raise CatalogError(f"{path}: {label}.conditions must not be empty")
        return ResearchPrincipleDetails(
            conclusion=_str(details["conclusion"], path, f"{label}.conclusion"),
            reason=_str(details["reason"], path, f"{label}.reason"),
            conditions=conditions,
        )
    if item_type == "rule":
        expected = {"rule", "applicability", "numbers_exceptions"}
        if set(details) != expected:
            raise CatalogError(
                f"{path}: {label} rule details keys must be {sorted(expected)}"
            )
        applicability = _string_list(
            details["applicability"], path, f"{label}.applicability"
        )
        if not applicability:
            raise CatalogError(f"{path}: {label}.applicability must not be empty")
        return ResearchRuleDetails(
            rule=_str(details["rule"], path, f"{label}.rule"),
            applicability=applicability,
            numbers_exceptions=_string_list(
                details["numbers_exceptions"],
                path,
                f"{label}.numbers_exceptions",
            ),
        )
    expected = {"definition", "distinguishing_conditions", "confusable_points"}
    if set(details) != expected:
        raise CatalogError(
            f"{path}: {label} identification details keys must be {sorted(expected)}"
        )
    distinguishing = _string_list(
        details["distinguishing_conditions"],
        path,
        f"{label}.distinguishing_conditions",
    )
    if not distinguishing:
        raise CatalogError(
            f"{path}: {label}.distinguishing_conditions must not be empty"
        )
    return ResearchIdentificationDetails(
        definition=_str(details["definition"], path, f"{label}.definition"),
        distinguishing_conditions=distinguishing,
        confusable_points=_string_list(
            details["confusable_points"], path, f"{label}.confusable_points"
        ),
    )


def _evidence_records(
    value: object,
    path: Path,
    label: str,
) -> tuple[ResearchEvidence, ...]:
    raw_records = _list(value, path, label)
    if not raw_records:
        raise CatalogError(f"{path}: {label} must not be empty")
    records: list[ResearchEvidence] = []
    for index, raw_record in enumerate(raw_records, start=1):
        record_label = f"{label}[{index}]"
        record = _mapping(raw_record, path, record_label)
        kind = _str(record.get("kind"), path, f"{record_label}.kind")
        if kind not in _EVIDENCE_KINDS:
            raise CatalogError(
                f"{path}: {record_label}.kind must be ledger, external, or codex"
            )
        supports = _string_list(
            record.get("supports"), path, f"{record_label}.supports"
        )
        if not supports or not set(supports) <= _EVIDENCE_SUPPORTS:
            raise CatalogError(
                f"{path}: {record_label}.supports must use question, answer, or details"
            )
        typed_supports = cast(tuple[ResearchEvidenceSupport, ...], supports)
        if kind == "ledger":
            expected = {"kind", "locator", "supports"}
            if set(record) != expected:
                raise CatalogError(
                    f"{path}: {record_label} ledger evidence keys must be {sorted(expected)}"
                )
            records.append(
                ResearchEvidence(
                    kind="ledger",
                    supports=typed_supports,
                    locator=_str(record["locator"], path, f"{record_label}.locator"),
                )
            )
        elif kind == "external":
            expected = {
                "kind",
                "source_class",
                "title",
                "locator",
                "url",
                "supports",
            }
            if set(record) != expected:
                raise CatalogError(
                    f"{path}: {record_label} external evidence keys must be {sorted(expected)}"
                )
            url = _str(record["url"], path, f"{record_label}.url")
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise CatalogError(
                    f"{path}: {record_label}.url must be an absolute HTTPS URL"
                )
            source_class = _str(
                record["source_class"], path, f"{record_label}.source_class"
            )
            if source_class not in _EXTERNAL_SOURCE_CLASSES:
                raise CatalogError(
                    f"{path}: {record_label}.source_class must be official or explanation"
                )
            records.append(
                ResearchEvidence(
                    kind="external",
                    supports=typed_supports,
                    locator=_str(record["locator"], path, f"{record_label}.locator"),
                    title=_str(record["title"], path, f"{record_label}.title"),
                    url=url,
                    source_class=cast(ResearchExternalSourceClass, source_class),
                )
            )
        else:
            expected = {"kind", "supplement", "supports"}
            if set(record) != expected:
                raise CatalogError(
                    f"{path}: {record_label} codex evidence keys must be {sorted(expected)}"
                )
            if "answer" in supports:
                raise CatalogError(
                    f"{path}: {record_label} codex evidence cannot support answer"
                )
            records.append(
                ResearchEvidence(
                    kind="codex",
                    supports=typed_supports,
                    supplement=_str(
                        record["supplement"], path, f"{record_label}.supplement"
                    ),
                )
            )
    if len(records) != len(set(records)):
        raise CatalogError(f"{path}: {label} must not contain duplicate records")
    return tuple(records)


def _has_provisional_answer_support(evidence: tuple[ResearchEvidence, ...]) -> bool:
    answer_sources = [item for item in evidence if "answer" in item.supports]
    if any(item.kind == "ledger" for item in answer_sources):
        return True
    if any(
        item.kind == "external" and item.source_class == "official"
        for item in answer_sources
    ):
        return True
    explanation_hosts = {
        cast(str, urlparse(cast(str, item.url)).hostname).casefold()
        for item in answer_sources
        if item.kind == "external"
        and item.source_class == "explanation"
        and urlparse(cast(str, item.url)).hostname is not None
    }
    return len(explanation_hosts) >= 2


def _question_revision(
    value: object,
    *,
    expected_revision: int,
    item_type: PrincipleType,
    path: Path,
    label: str,
) -> ResearchQuestionRevision:
    revision = _mapping(value, path, label)
    _exact_keys(revision, _QUESTION_REVISION_FIELDS, path, label)
    number = _int(revision["revision"], path, f"{label}.revision")
    if number != expected_revision:
        raise CatalogError(
            f"{path}: {label}.revision must be {expected_revision}"
        )
    state = _str(revision["state"], path, f"{label}.state")
    if state not in _QUESTION_STATES:
        raise CatalogError(
            f"{path}: {label}.state must be provisional_answer or pending"
        )
    prompt = _question_text(revision["prompt"], path, f"{label}.prompt")
    if (
        not prompt.endswith(_QUESTION_SUFFIX)
        or prompt.count(_QUESTION_SUFFIX) != 1
        or any(
            cue in prompt
            for cue in _PROMPT_FORBIDDEN | _ANSWER_CUES | _SYMBOL_CUES
        )
    ):
        raise CatalogError(
            f"{path}: {label}.prompt must use the single-axis binary form "
            f"ending {_QUESTION_SUFFIX!r}"
        )
    choices = _mapping(revision["choices"], path, f"{label}.choices")
    _exact_keys(choices, {"A", "B"}, path, f"{label}.choices")
    choice_a = _question_text(choices["A"], path, f"{label}.choices.A")
    choice_b = _question_text(choices["B"], path, f"{label}.choices.B")
    if any(
        cue in f"{choice_a} {choice_b}"
        for cue in _CHOICE_CUES | _ANSWER_CUES | _SYMBOL_CUES
    ):
        raise CatalogError(f"{path}: {label}.choices contain a forbidden cue")
    if choice_a in {"○", "×"} or choice_b in {"○", "×"}:
        raise CatalogError(f"{path}: {label}.choices contain a forbidden cue")
    if max(len(choice_a), len(choice_b)) > 40:
        raise CatalogError(
            f"{path}: {label}.choices must be 40 characters or fewer"
        )
    if abs(len(choice_a) - len(choice_b)) > 10:
        raise CatalogError(f"{path}: {label}.choices must be similar in length")
    if _normalized(choice_a) == _normalized(choice_b):
        raise CatalogError(f"{path}: {label}.choices must be distinct")

    raw_answer = revision["answer"]
    if raw_answer is not None and raw_answer not in {"A", "B"}:
        raise CatalogError(f"{path}: {label}.answer must be A, B, or null")
    if state == "pending" and raw_answer is not None:
        raise CatalogError(f"{path}: {label}.answer must be null while pending")
    if state == "provisional_answer" and raw_answer not in {"A", "B"}:
        raise CatalogError(
            f"{path}: {label}.answer must be A or B for provisional_answer"
        )
    evidence = _evidence_records(
        revision["evidence"], path, f"{label}.evidence"
    )
    if state == "provisional_answer" and not _has_provisional_answer_support(evidence):
        raise CatalogError(
            f"{path}: {label} provisional answer requires ledger answer support, "
            "one official external answer source, or two independent explanation hosts"
        )
    return ResearchQuestionRevision(
        revision=number,
        state=cast(ResearchQuestionState, state),
        prompt=prompt,
        choice_a=choice_a,
        choice_b=choice_b,
        answer=cast(ChoiceLabel | None, raw_answer),
        details=_question_details(
            revision["details"], item_type, path, f"{label}.details"
        ),
        evidence=evidence,
    )


def _details_payload(details: ResearchQuestionDetails) -> dict[str, object]:
    if isinstance(details, ResearchPrincipleDetails):
        return {
            "conclusion": details.conclusion,
            "reason": details.reason,
            "conditions": list(details.conditions),
        }
    if isinstance(details, ResearchRuleDetails):
        return {
            "rule": details.rule,
            "applicability": list(details.applicability),
            "numbers_exceptions": list(details.numbers_exceptions),
        }
    return {
        "definition": details.definition,
        "distinguishing_conditions": list(details.distinguishing_conditions),
        "confusable_points": list(details.confusable_points),
    }


def _evidence_payload(evidence: ResearchEvidence) -> dict[str, object]:
    if evidence.kind == "ledger":
        return {
            "kind": evidence.kind,
            "locator": evidence.locator,
            "supports": list(evidence.supports),
        }
    if evidence.kind == "external":
        return {
            "kind": evidence.kind,
            "source_class": evidence.source_class,
            "title": evidence.title,
            "locator": evidence.locator,
            "url": evidence.url,
            "supports": list(evidence.supports),
        }
    return {
        "kind": evidence.kind,
        "supplement": evidence.supplement,
        "supports": list(evidence.supports),
    }


def _question_revision_payload(revision: ResearchQuestionRevision) -> dict[str, object]:
    return {
        "revision": revision.revision,
        "state": revision.state,
        "prompt": revision.prompt,
        "choices": {"A": revision.choice_a, "B": revision.choice_b},
        "answer": revision.answer,
        "details": _details_payload(revision.details),
        "evidence": [_evidence_payload(item) for item in revision.evidence],
    }


RecordT = TypeVar("RecordT", ResearchQuestionRecord, ResearchCoverageRecord)


def _raw_release_content_sha256(
    release_id: str,
    *,
    row_name: str,
    items: dict[str, Any],
    revisions: dict[str, int],
    active: tuple[str, ...] | list[str],
) -> str:
    rows: list[dict[str, object]] = []
    for key in sorted(revisions):
        record = cast(dict[str, Any], items[key])
        history = cast(list[dict[str, object]], record["revision_history"])
        for revision in history[: revisions[key]]:
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


def research_question_release_sha256(
    release_id: str,
    items: dict[str, Any],
    revisions: dict[str, int],
    active: tuple[str, ...] | list[str],
) -> str:
    """Hash raw question-ledger items for a production release entry."""

    return _raw_release_content_sha256(
        release_id,
        row_name="questions",
        items=items,
        revisions=revisions,
        active=active,
    )


def research_coverage_release_sha256(
    release_id: str,
    items: dict[str, Any],
    revisions: dict[str, int],
    active: tuple[str, ...] | list[str],
) -> str:
    """Hash raw candidate-coverage items for a production release entry."""

    return _raw_release_content_sha256(
        release_id,
        row_name="assignments",
        items=items,
        revisions=revisions,
        active=active,
    )


def _release_content_sha256(
    release_id: str,
    *,
    row_name: str,
    items: dict[str, RecordT],
    revisions: dict[str, int],
    active: tuple[str, ...],
    revision_payload: Callable[[Any], dict[str, object]],
) -> str:
    rows: list[dict[str, object]] = []
    for key in sorted(revisions):
        record = items[key]
        for revision in record.revision_history[: revisions[key]]:
            row = {
                "key": key,
                "code": record.code,
                **revision_payload(revision),
            }
            if isinstance(record, ResearchQuestionRecord):
                row["type"] = record.type
            rows.append(row)
    canonical = json.dumps(
        {"id": release_id, "active": sorted(active), row_name: rows},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _release_watermarks(
    value: object,
    *,
    expected_number: int,
    release_prefix: str,
    release_pattern: re.Pattern[str],
    previous: dict[str, int],
    previous_active: tuple[str, ...],
    items: dict[str, RecordT],
    path: Path,
    label: str,
) -> tuple[str, tuple[str, ...], dict[str, int], str]:
    release = _mapping(value, path, label)
    _exact_keys(release, _RELEASE_FIELDS, path, label)
    release_id = _str(release["id"], path, f"{label}.id")
    expected_id = f"{release_prefix}{expected_number}"
    if release_id != expected_id or not release_pattern.fullmatch(release_id):
        raise CatalogError(f"{path}: {label}.id must be {expected_id}")
    active = _string_list(release["active"], path, f"{label}.active")
    if active != tuple(sorted(active)):
        raise CatalogError(f"{path}: {label}.active must be sorted")
    unknown_active = sorted(set(active) - set(items))
    if unknown_active:
        raise CatalogError(
            f"{path}: {label}.active references unknown items: {unknown_active}"
        )
    raw_revisions = _mapping(release["revisions"], path, f"{label}.revisions")
    unknown = sorted(set(raw_revisions) - set(items))
    if unknown:
        raise CatalogError(f"{path}: {label} references unknown items: {unknown}")
    revisions: dict[str, int] = {}
    for key, raw_revision in raw_revisions.items():
        revision = _int(raw_revision, path, f"{label}.revisions.{key}")
        if revision < 1 or revision > len(items[key].revision_history):
            raise CatalogError(
                f"{path}: {label}.revisions.{key} must cover an existing revision"
            )
        revisions[key] = revision
    unreleased_active = sorted(set(active) - set(revisions))
    if unreleased_active:
        raise CatalogError(
            f"{path}: {label}.active must have cumulative revision watermarks: "
            f"{unreleased_active}"
        )
    dropped = sorted(set(previous) - set(revisions))
    decreased = sorted(
        key for key, old in previous.items() if revisions.get(key, 0) < old
    )
    if dropped or decreased:
        raise CatalogError(
            f"{path}: {label} cumulative revision watermarks must not drop or decrease"
        )
    if revisions == previous and active == previous_active:
        raise CatalogError(
            f"{path}: {label} must advance a revision or change active items"
        )
    digest = _str(release["content_sha256"], path, f"{label}.content_sha256")
    if not _SHA256.fullmatch(digest):
        raise CatalogError(f"{path}: {label}.content_sha256 must be a SHA-256")
    return release_id, active, revisions, digest


def _load_research_questions(
    catalog: Catalog,
    path: Path,
    *,
    enforce_current_active: bool,
) -> ResearchQuestionRegistry:
    document = _load_yaml(path)
    _exact_keys(document, {"version", "releases", "items"}, path, "document")
    if _int(document["version"], path, "version") != 1:
        raise CatalogError(f"{path}: version must be 1")
    by_id = {item.id: item for item in catalog.principles}
    known_identities = {
        **catalog.identities.retired,
        **catalog.identities.active,
    }
    current_active = {
        item.id: item
        for item in catalog.principles
        if item.editorial_status != "source_checked"
    }
    raw_items = _mapping(document["items"], path, "items")
    missing = (
        sorted(set(current_active) - set(raw_items))
        if enforce_current_active
        else []
    )
    unknown = sorted(set(raw_items) - set(known_identities))
    if missing or unknown:
        raise CatalogError(
            f"{path}: items must retain known research history and cover current "
            "active non-source_checked items exactly once; "
            f"missing={missing}, unknown={unknown}"
        )

    items: dict[str, ResearchQuestionRecord] = {}
    for key in raw_items:
        item = by_id.get(key)
        raw_record = _mapping(raw_items[key], path, f"items.{key}")
        _exact_keys(raw_record, _QUESTION_ITEM_FIELDS, path, f"items.{key}")
        code = _str(raw_record["code"], path, f"items.{key}.code")
        item_type = _str(raw_record["type"], path, f"items.{key}.type")
        if item_type not in {"principle", "rule", "identification"}:
            raise CatalogError(
                f"{path}: items.{key}.type must be principle, rule, or identification"
            )
        expected_code = known_identities[key].code
        if code != expected_code or (item is not None and code != item.code):
            raise CatalogError(
                f"{path}: {key} published code must remain {expected_code!r}"
            )
        if item is not None and item_type != item.type:
            raise CatalogError(
                f"{path}: {key} type must remain {item.type!r}"
            )
        raw_history = _list(
            raw_record["revision_history"], path, f"items.{key}.revision_history"
        )
        if not raw_history:
            raise CatalogError(
                f"{path}: items.{key}.revision_history must not be empty"
            )
        history = tuple(
            _question_revision(
                value,
                expected_revision=index,
                item_type=cast(PrincipleType, item_type),
                path=path,
                label=f"items.{key}.revision_history[{index}]",
            )
            for index, value in enumerate(raw_history, start=1)
        )
        fingerprints = {
            json.dumps(
                {
                    key: value
                    for key, value in _question_revision_payload(revision).items()
                    if key != "revision"
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for revision in history
        }
        if len(fingerprints) != len(history):
            raise CatalogError(
                f"{path}: items.{key}.revision_history repeats revision content"
            )
        items[key] = ResearchQuestionRecord(
            code=code,
            type=cast(PrincipleType, item_type),
            revision_history=history,
        )

    raw_releases = _list(document["releases"], path, "releases")
    if not raw_releases:
        raise CatalogError(f"{path}: releases must not be empty")
    releases: list[ResearchQuestionRelease] = []
    previous: dict[str, int] = {}
    previous_active: tuple[str, ...] = ()
    for index, raw_release in enumerate(raw_releases, start=1):
        label = f"releases[{index}]"
        release_id, active, revisions, digest = _release_watermarks(
            raw_release,
            expected_number=index,
            release_prefix="steel-research-questions-v",
            release_pattern=_QUESTION_RELEASE_ID,
            previous=previous,
            previous_active=previous_active,
            items=items,
            path=path,
            label=label,
        )
        expected_digest = _release_content_sha256(
            release_id,
            row_name="questions",
            items=items,
            revisions=revisions,
            active=active,
            revision_payload=_question_revision_payload,
        )
        if digest != expected_digest:
            raise CatalogError(f"{path}: {label} differs from its audited snapshot")
        releases.append(
            ResearchQuestionRelease(
                id=release_id,
                active=active,
                revisions=revisions,
                content_sha256=digest,
            )
        )
        previous = revisions
        previous_active = active
    expected_latest = {
        key: len(record.revision_history) for key, record in items.items()
    }
    if previous != expected_latest:
        raise CatalogError(
            f"{path}: latest release must publish every current question revision"
        )
    expected_active = set(current_active)
    if enforce_current_active and set(previous_active) != expected_active:
        missing = sorted(expected_active - set(previous_active))
        extra = sorted(set(previous_active) - expected_active)
        raise CatalogError(
            f"{path}: latest active must cover current non-source_checked items "
            f"exactly once; missing={missing}, extra={extra}"
        )
    return ResearchQuestionRegistry(items=items, releases=tuple(releases))


def load_research_questions(
    catalog: Catalog,
    path: Path = RESEARCH_QUESTIONS_PATH,
) -> ResearchQuestionRegistry:
    """Load the append-only provisional question ledger."""

    return _load_research_questions(
        catalog,
        path,
        enforce_current_active=True,
    )


def _coverage_revision(
    value: object,
    *,
    expected_revision: int,
    item_type: PrincipleType,
    path: Path,
    label: str,
) -> ResearchCoverageRevision:
    revision = _mapping(value, path, label)
    _exact_keys(revision, _COVERAGE_REVISION_FIELDS, path, label)
    number = _int(revision["revision"], path, f"{label}.revision")
    if number != expected_revision:
        raise CatalogError(
            f"{path}: {label}.revision must be {expected_revision}"
        )
    tier = _int(revision["tier"], path, f"{label}.tier")
    if tier not in _COVERAGE_TIERS:
        raise CatalogError(f"{path}: {label}.tier must be 1, 2, or 3")
    reasons = _string_list(revision["reasons"], path, f"{label}.reasons")
    if not reasons or not set(reasons) <= _COVERAGE_REASONS:
        raise CatalogError(f"{path}: {label}.reasons are invalid")
    base_reasons = {
        1: {"coverage_representative"},
        2: {"standard_application"},
        3: {"exception_detail", "integrated_judgment"},
    }
    if not set(reasons) & base_reasons[tier]:
        raise CatalogError(
            f"{path}: {label}.reasons must include a reason for tier {tier}"
        )
    reasons_for_other_tiers = set().union(
        *(values for candidate, values in base_reasons.items() if candidate != tier)
    )
    if set(reasons) & reasons_for_other_tiers:
        raise CatalogError(
            f"{path}: {label}.reasons include a reason for another tier"
        )
    if "basic_identification" in reasons and (
        item_type != "identification" or tier == 3
    ):
        raise CatalogError(
            f"{path}: {label}.basic_identification requires tier 1 or 2 identification"
        )
    return ResearchCoverageRevision(
        revision=number,
        tier=cast(CoverageTier, tier),
        reasons=cast(tuple[CoverageReason, ...], reasons),
    )


def _coverage_revision_payload(revision: ResearchCoverageRevision) -> dict[str, object]:
    return {
        "revision": revision.revision,
        "tier": revision.tier,
        "reasons": list(revision.reasons),
    }


def _validate_research_prerequisites(
    catalog: Catalog,
    items: dict[str, ResearchCoverageRecord],
    path: Path,
) -> None:
    formal = catalog.coverage.schemes[catalog.coverage.current].assignments
    tiers = {key: assignment.tier for key, assignment in formal.items()}
    tiers.update({key: record.current.tier for key, record in items.items()})
    by_id = {item.id: item for item in catalog.principles}
    for key, record in items.items():
        for prerequisite in by_id[key].prerequisites:
            prerequisite_tier = tiers.get(prerequisite)
            if prerequisite_tier is None:
                raise CatalogError(
                    f"{path}: {key} has an unassigned prerequisite: {prerequisite}"
                )
            if prerequisite_tier > record.current.tier:
                raise CatalogError(
                    f"{path}: {key} has prerequisite in a later candidate tier: "
                    f"{prerequisite}"
                )


def _validate_global_foundation(
    catalog: Catalog,
    items: dict[str, ResearchCoverageRecord],
    path: Path,
) -> None:
    formal = catalog.coverage.schemes[catalog.coverage.current].assignments
    foundation_keys = [
        key for key, assignment in formal.items() if assignment.tier == 1
    ] + [key for key, record in items.items() if record.current.tier == 1]
    counts: dict[str, int] = {}
    for key in foundation_keys:
        subtopic = catalog.taxonomy.assignments[key]
        counts[subtopic] = counts.get(subtopic, 0) + 1
    all_subtopics = {
        subtopic.id for group in catalog.taxonomy.groups for subtopic in group.subtopics
    }
    missing = sorted(all_subtopics - set(counts))
    duplicates = sorted(key for key, count in counts.items() if count != 1)
    extras = sorted(set(counts) - all_subtopics)
    if missing or duplicates or extras:
        raise CatalogError(
            f"{path}: global foundation must cover every subtopic exactly once; "
            f"missing={missing}, duplicates={duplicates}, extra={extras}"
        )


def _load_research_coverage(
    catalog: Catalog,
    questions: ResearchQuestionRegistry,
    path: Path,
    *,
    enforce_current_projection: bool,
) -> ResearchCoverageRegistry:
    document = _load_yaml(path)
    _exact_keys(document, {"version", "releases", "items"}, path, "document")
    if _int(document["version"], path, "version") != 1:
        raise CatalogError(f"{path}: version must be 1")
    raw_items = _mapping(document["items"], path, "items")
    missing = sorted(set(questions.items) - set(raw_items))
    extra = sorted(set(raw_items) - set(questions.items))
    if extra or (enforce_current_projection and missing):
        raise CatalogError(
            f"{path}: items must assign every research question exactly once; "
            f"missing={missing}, extra={extra}"
        )
    items: dict[str, ResearchCoverageRecord] = {}
    for key in raw_items:
        raw_record = _mapping(raw_items[key], path, f"items.{key}")
        _exact_keys(raw_record, _COVERAGE_ITEM_FIELDS, path, f"items.{key}")
        code = _str(raw_record["code"], path, f"items.{key}.code")
        if code != questions.items[key].code:
            raise CatalogError(
                f"{path}: {key} published code must remain {questions.items[key].code!r}"
            )
        raw_history = _list(
            raw_record["revision_history"], path, f"items.{key}.revision_history"
        )
        if not raw_history:
            raise CatalogError(
                f"{path}: items.{key}.revision_history must not be empty"
            )
        history = tuple(
            _coverage_revision(
                value,
                expected_revision=index,
                item_type=questions.items[key].type,
                path=path,
                label=f"items.{key}.revision_history[{index}]",
            )
            for index, value in enumerate(raw_history, start=1)
        )
        fingerprints = {
            json.dumps(
                {
                    key: value
                    for key, value in _coverage_revision_payload(revision).items()
                    if key != "revision"
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for revision in history
        }
        if len(fingerprints) != len(history):
            raise CatalogError(
                f"{path}: items.{key}.revision_history repeats revision content"
            )
        items[key] = ResearchCoverageRecord(code=code, revision_history=history)

    raw_releases = _list(document["releases"], path, "releases")
    if not raw_releases:
        raise CatalogError(f"{path}: releases must not be empty")
    releases: list[ResearchCoverageRelease] = []
    previous: dict[str, int] = {}
    previous_active: tuple[str, ...] = ()
    for index, raw_release in enumerate(raw_releases, start=1):
        label = f"releases[{index}]"
        release_id, active, revisions, digest = _release_watermarks(
            raw_release,
            expected_number=index,
            release_prefix="steel-research-coverage-v",
            release_pattern=_COVERAGE_RELEASE_ID,
            previous=previous,
            previous_active=previous_active,
            items=items,
            path=path,
            label=label,
        )
        expected_digest = _release_content_sha256(
            release_id,
            row_name="assignments",
            items=items,
            revisions=revisions,
            active=active,
            revision_payload=_coverage_revision_payload,
        )
        if digest != expected_digest:
            raise CatalogError(f"{path}: {label} differs from its audited snapshot")
        releases.append(
            ResearchCoverageRelease(
                id=release_id,
                active=active,
                revisions=revisions,
                content_sha256=digest,
            )
        )
        previous = revisions
        previous_active = active
    expected_latest = {
        key: len(record.revision_history) for key, record in items.items()
    }
    if previous != expected_latest:
        raise CatalogError(
            f"{path}: latest release must publish every current coverage revision"
        )
    if enforce_current_projection:
        expected_active = set(questions.active_keys)
        if set(previous_active) != expected_active:
            missing = sorted(expected_active - set(previous_active))
            extra = sorted(set(previous_active) - expected_active)
            raise CatalogError(
                f"{path}: latest active must match current research questions "
                f"exactly once; missing={missing}, extra={extra}"
            )
        active_items = {key: items[key] for key in previous_active}
        _validate_research_prerequisites(catalog, active_items, path)
        _validate_global_foundation(catalog, active_items, path)
    return ResearchCoverageRegistry(items=items, releases=tuple(releases))


def load_research_coverage(
    catalog: Catalog,
    questions: ResearchQuestionRegistry,
    path: Path = RESEARCH_COVERAGE_TIERS_PATH,
) -> ResearchCoverageRegistry:
    """Load candidate tiers without mutating the issued coverage scheme."""

    return _load_research_coverage(
        catalog,
        questions,
        path,
        enforce_current_projection=True,
    )


def validate_research_question_history(
    catalog: Catalog,
    previous_path: Path,
    current_path: Path = RESEARCH_QUESTIONS_PATH,
) -> None:
    """Reject changes to any released provisional question or code."""

    previous = _load_research_questions(
        catalog,
        previous_path,
        enforce_current_active=False,
    )
    current = load_research_questions(catalog, current_path)
    for key, past in previous.items.items():
        present = current.items.get(key)
        if (
            present is None
            or present.code != past.code
            or present.type != past.type
        ):
            raise CatalogError(
                f"{current_path}: past question code must not change or be removed: {key}"
            )
        if present.revision_history[: len(past.revision_history)] != past.revision_history:
            raise CatalogError(
                f"{current_path}: past question revision must not change or be removed: {key}"
            )
    if current.releases[: len(previous.releases)] != previous.releases:
        raise CatalogError(
            f"{current_path}: past question releases must not change or be removed"
        )


def validate_research_coverage_history(
    catalog: Catalog,
    questions: ResearchQuestionRegistry,
    previous_path: Path,
    current_path: Path = RESEARCH_COVERAGE_TIERS_PATH,
) -> None:
    """Reject changes to any released candidate tier or code."""

    previous = _load_research_coverage(
        catalog,
        questions,
        previous_path,
        enforce_current_projection=False,
    )
    current = load_research_coverage(catalog, questions, current_path)
    for key, past in previous.items.items():
        present = current.items.get(key)
        if present is None or present.code != past.code:
            raise CatalogError(
                f"{current_path}: past coverage code must not change or be removed: {key}"
            )
        if present.revision_history[: len(past.revision_history)] != past.revision_history:
            raise CatalogError(
                f"{current_path}: past coverage revision must not change or be removed: {key}"
            )
    if current.releases[: len(previous.releases)] != previous.releases:
        raise CatalogError(
            f"{current_path}: past coverage releases must not change or be removed"
        )
