"""Validated models for the canonical principle catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


PrincipleType = Literal["principle", "rule", "identification"]
EditorialStatus = Literal["draft", "source_checked", "source_gap"]
PublicProgress = Literal["unstarted", "learning", "reviewing", "retained_14d"]
ChoiceLabel = Literal["A", "B"]


@dataclass(frozen=True)
class SourceRef:
    pages: tuple[int, ...]
    question_codes: tuple[str, ...]


@dataclass(frozen=True)
class BinaryQuestion:
    prompt: str
    choice_a: str
    choice_b: str
    correct: ChoiceLabel


@dataclass(frozen=True)
class Principle:
    id: str
    section_id: str
    section_title: str
    section_order: int
    order: int
    type: PrincipleType
    principle: str
    question: BinaryQuestion | None
    conclusion: str
    reason: str
    conditions: tuple[str, ...]
    source: SourceRef
    prerequisites: tuple[str, ...]
    editorial_status: EditorialStatus


@dataclass(frozen=True)
class CatalogManifest:
    source_title: str
    source_sha256: str
    first_page: int
    last_page: int
    audited_pages: tuple[int, ...]
    section_files: tuple[Path, ...]
    expected_total: int
    expected_status_counts: dict[EditorialStatus, int]
    expected_answer_counts: dict[ChoiceLabel, int]
    question_audit_sha256: str
    next_print_number: int
    print_numbers: dict[str, int]
    print_registry_sha256: str


@dataclass(frozen=True)
class SourceAudit:
    table_pages: tuple[int, ...]
    table_row_count: int
    primary_question_codes: tuple[str, ...]
    page_kinds: dict[str, tuple[int, ...]]


@dataclass(frozen=True)
class Catalog:
    manifest: CatalogManifest
    audit: SourceAudit
    principles: tuple[Principle, ...]


@dataclass(frozen=True)
class PublicProgressProjection:
    items: dict[str, PublicProgress]
