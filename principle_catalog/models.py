"""Validated models for the canonical principle catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


PrincipleType = Literal["principle", "rule", "identification"]
EditorialStatus = Literal["draft", "source_checked", "source_gap"]
PublicProgress = Literal["unstarted", "learning", "reviewing", "retained_14d"]
ChoiceLabel = Literal["A", "B"]
AuthoritativeSourceKind = Literal[
    "law",
    "notification",
    "jis",
    "aij",
    "government_spec",
]
SourceSupport = Literal["statement", "explanation", "conditions"]
StatementSourceStatus = Literal["verified", "gap", "unreviewed"]
CompletenessStatus = Literal["complete", "partial", "missing", "unreviewed"]
MigrationOperation = Literal["split", "merge", "rename"]
QuestionEditionStatus = Literal["archived", "current"]
CoverageTier = Literal[1, 2, 3]
CoverageSchemeStatus = Literal["archived", "current"]
CoverageReason = Literal[
    "coverage_representative",
    "prerequisite",
    "standard_application",
    "basic_identification",
    "exception_detail",
    "integrated_judgment",
]


@dataclass(frozen=True)
class AuthoritativeSource:
    kind: AuthoritativeSourceKind
    title: str
    locator: str
    url: str | None
    supports: tuple[SourceSupport, ...]


@dataclass(frozen=True)
class SourceRef:
    pages: tuple[int, ...]
    question_codes: tuple[str, ...]
    authoritative_sources: tuple[AuthoritativeSource, ...] = ()

    @property
    def kinds(self) -> tuple[str, ...]:
        """Return stable values suitable for the public source-kind filter."""

        kinds = dict.fromkeys(
            ("pdf", *(source.kind for source in self.authoritative_sources))
        )
        return tuple(kinds)


@dataclass(frozen=True)
class ContentVerification:
    statement_source: StatementSourceStatus
    explanation_completeness: CompletenessStatus
    conditions_completeness: CompletenessStatus


@dataclass(frozen=True)
class RuleDisplayContent:
    rule: str
    applicability: tuple[str, ...]
    numbers_exceptions: tuple[str, ...]


@dataclass(frozen=True)
class IdentificationDisplayContent:
    definition: str
    distinguishing_conditions: tuple[str, ...]
    confusable_points: tuple[str, ...]


TypedDisplayContent = RuleDisplayContent | IdentificationDisplayContent


@dataclass(frozen=True)
class DisplayFacet:
    label: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class CardDisplayFacets:
    primary: DisplayFacet
    secondary: DisplayFacet
    tertiary: DisplayFacet
    typed: bool


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
    related: tuple[str, ...] = ()
    code: str = ""
    display_content: TypedDisplayContent | None = None
    verification: ContentVerification = ContentVerification(
        statement_source="unreviewed",
        explanation_completeness="unreviewed",
        conditions_completeness="unreviewed",
    )

    @property
    def key(self) -> str:
        """The immutable internal key persisted by private study data."""

        return self.id

    @property
    def source_collection_id(self) -> str:
        """Physical YAML collection; deliberately separate from display taxonomy."""

        return self.section_id

    @property
    def source_collection_title(self) -> str:
        return self.section_title


@dataclass(frozen=True)
class AuthoritativeSourceSchema:
    allowed_kinds: tuple[AuthoritativeSourceKind, ...]
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    allowed_supports: tuple[SourceSupport, ...]


@dataclass(frozen=True)
class ContentReviewSchema:
    statement_source: tuple[StatementSourceStatus, ...]
    explanation_completeness: tuple[CompletenessStatus, ...]
    conditions_completeness: tuple[CompletenessStatus, ...]


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
    question_order_sha256: str
    taxonomy_audit_sha256: str
    prerequisites_audit_sha256: str
    identities_audit_sha256: str
    migration_audit_sha256: str
    coverage_tiers_audit_sha256: str
    next_print_number: int
    print_numbers: dict[str, int]
    print_registry_sha256: str
    projection_paths: dict[str, Path]
    authoritative_source_schema: AuthoritativeSourceSchema
    content_review_schema: ContentReviewSchema


@dataclass(frozen=True)
class SourceAudit:
    table_pages: tuple[int, ...]
    table_row_count: int
    primary_question_codes: tuple[str, ...]
    page_kinds: dict[str, tuple[int, ...]]

    def kind_for_page(self, page: int) -> str:
        for kind, pages in self.page_kinds.items():
            if page in pages:
                return kind
        raise KeyError(page)


@dataclass(frozen=True)
class TypeDisplayLabels:
    primary_label: str
    rationale_label: str
    qualifiers_label: str


@dataclass(frozen=True)
class DisplaySchema:
    primary_field: str
    rationale_field: str
    qualifiers_field: str
    types: dict[PrincipleType, TypeDisplayLabels]


@dataclass(frozen=True)
class TaxonomySubtopic:
    id: str
    title: str
    order: int


@dataclass(frozen=True)
class TaxonomyGroup:
    id: str
    title: str
    order: int
    subtopics: tuple[TaxonomySubtopic, ...]


@dataclass(frozen=True)
class TaxonomyProjection:
    display_schema: DisplaySchema
    groups: tuple[TaxonomyGroup, ...]
    assignments: dict[str, str]


@dataclass(frozen=True)
class PrincipleIdentity:
    key: str
    code: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class IdentityRegistry:
    active: dict[str, PrincipleIdentity]
    retired: dict[str, PrincipleIdentity]


@dataclass(frozen=True)
class MigrationRecord:
    operation: MigrationOperation
    targets: tuple[str, ...]
    progress_policy: str
    legacy_section: str


@dataclass(frozen=True)
class MigrationRegistry:
    aliases: dict[str, tuple[str, ...]]
    retired: dict[str, MigrationRecord]


@dataclass(frozen=True)
class QuestionEdition:
    id: str
    status: QuestionEditionStatus
    content_sha256: str
    assignments: dict[str, int]

    def reference(self, key: str) -> str:
        return f"{self.id} Q{self.assignments[key]:03d}"


@dataclass(frozen=True)
class QuestionEditionRegistry:
    current: str
    editions: dict[str, QuestionEdition]


@dataclass(frozen=True)
class CoverageTierDefinition:
    tier: CoverageTier
    slug: str
    label: str


@dataclass(frozen=True)
class CoverageAssignment:
    tier: CoverageTier
    introduction_order: int
    reasons: tuple[CoverageReason, ...]


@dataclass(frozen=True)
class CoverageConstraints:
    tier_counts: dict[CoverageTier, int]
    answer_counts: dict[CoverageTier, dict[ChoiceLabel, int]]
    type_counts: dict[CoverageTier, dict[PrincipleType, int]]
    max_same_answer_run: int
    foundation_covers_all_published_subtopics: bool


@dataclass(frozen=True)
class CoverageScheme:
    id: str
    status: CoverageSchemeStatus
    content_sha256: str
    constraints: CoverageConstraints
    assignments: dict[str, CoverageAssignment]


@dataclass(frozen=True)
class CoverageRegistry:
    current: str
    tiers: dict[CoverageTier, CoverageTierDefinition]
    schemes: dict[str, CoverageScheme]


@dataclass(frozen=True)
class Catalog:
    manifest: CatalogManifest
    audit: SourceAudit
    principles: tuple[Principle, ...]
    taxonomy: TaxonomyProjection
    identities: IdentityRegistry
    migration: MigrationRegistry
    question_editions: QuestionEditionRegistry
    coverage: CoverageRegistry


@dataclass(frozen=True)
class PublicProgressProjection:
    items: dict[str, PublicProgress]
