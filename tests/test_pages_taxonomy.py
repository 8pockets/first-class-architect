"""Public Pages taxonomy and identity contracts."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace
from html import escape
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

import principle_catalog.site as site_module
from principle_catalog.catalog import (
    display_facets,
    display_principles,
    load_catalog,
    load_public_progress,
    resolve_principle,
)
from principle_catalog.models import (
    AuthoritativeSource,
    IdentificationDisplayContent,
    ResearchCoverageRecord,
    ResearchCoverageRevision,
    ResearchEvidence,
    ResearchIdentificationDetails,
    ResearchPrincipleDetails,
    ResearchQuestionRecord,
    ResearchQuestionRevision,
    ResearchRuleDetails,
    RuleDisplayContent,
)
from principle_catalog.research import (
    ResearchQueryRelease,
    _release_content_sha256,
    load_research_queries,
)
from principle_catalog.research_questions import (
    load_research_coverage,
    load_research_questions,
)
from principle_catalog.site import build_site


class _TaxonomyOutline(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.section_depth = 0
        self.group_depths: list[int] = []
        self.subtopic_depths: list[int] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag == "section" and "data-taxonomy-group" in attributes:
            self.group_depths.append(self.section_depth)
        if tag == "section" and "data-taxonomy-subtopic" in attributes:
            self.subtopic_depths.append(self.section_depth)
        if tag == "section":
            self.section_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "section":
            self.section_depth -= 1


def _built_html(tmp_path: Path) -> str:
    output = tmp_path / "site"
    build_site(output, "https://8pockets.github.io/first-class-architect/")
    return (output / "index.html").read_text(encoding="utf-8")


def _card_html(html: str, public_code: str) -> str:
    return html.split(f'id="{public_code}"', maxsplit=1)[1].split(
        "</article>", maxsplit=1
    )[0]


def _identity_identifiers(catalog, published_keys: set[str]) -> set[str]:
    identifiers: set[str] = set()
    issued_keys = {
        key
        for edition in catalog.question_editions.editions.values()
        for key in edition.assignments
    }
    for identity in catalog.identities.active.values():
        if identity.key in published_keys or identity.key in issued_keys:
            identifiers.update((identity.key, identity.code, *identity.aliases))
    for identity in catalog.identities.retired.values():
        if identity.key in issued_keys:
            identifiers.update((identity.key, identity.code, *identity.aliases))
    return identifiers


def _patch_research_registries_for_catalog(
    monkeypatch,
    catalog,
    changed_catalog,
) -> None:
    questions = load_research_questions(catalog)
    coverage = load_research_coverage(catalog, questions)
    question_items = dict(questions.items)
    coverage_items = dict(coverage.items)
    formal_coverage = catalog.coverage.schemes[catalog.coverage.current].assignments
    active_items = tuple(
        item
        for item in changed_catalog.principles
        if item.editorial_status != "source_checked"
    )
    for item in active_items:
        if item.id in question_items:
            continue
        assert item.question is not None
        if item.type == "principle":
            details = ResearchPrincipleDetails(
                conclusion=item.conclusion,
                reason=item.reason,
                conditions=item.conditions,
            )
        elif item.type == "rule":
            assert isinstance(item.display_content, RuleDisplayContent)
            details = ResearchRuleDetails(
                rule=item.display_content.rule,
                applicability=item.display_content.applicability,
                numbers_exceptions=item.display_content.numbers_exceptions,
            )
        else:
            assert isinstance(item.display_content, IdentificationDisplayContent)
            details = ResearchIdentificationDetails(
                definition=item.display_content.definition,
                distinguishing_conditions=(
                    item.display_content.distinguishing_conditions
                ),
                confusable_points=item.display_content.confusable_points,
            )
        question_items[item.id] = ResearchQuestionRecord(
            code=item.code,
            type=item.type,
            revision_history=(
                ResearchQuestionRevision(
                    revision=1,
                    state="provisional_answer",
                    prompt=item.question.prompt,
                    choice_a=item.question.choice_a,
                    choice_b=item.question.choice_b,
                    answer=item.question.correct,
                    details=details,
                    evidence=(
                        ResearchEvidence(
                            kind="ledger",
                            locator="taxonomy transition fixture",
                            supports=("question", "answer", "details"),
                        ),
                    ),
                ),
            ),
        )
        formal = formal_coverage[item.id]
        coverage_items[item.id] = ResearchCoverageRecord(
            code=item.code,
            revision_history=(
                ResearchCoverageRevision(
                    revision=1,
                    tier=formal.tier,
                    reasons=formal.reasons,
                ),
            ),
        )

    active = tuple(sorted(item.id for item in active_items))
    question_revisions = {
        **questions.releases[-1].revisions,
        **{key: 1 for key in active if key not in questions.items},
    }
    coverage_revisions = {
        **coverage.releases[-1].revisions,
        **{key: 1 for key in active if key not in coverage.items},
    }
    changed_questions = replace(
        questions,
        items=question_items,
        releases=(
            *questions.releases[:-1],
            replace(
                questions.releases[-1],
                active=active,
                revisions=question_revisions,
            ),
        ),
    )
    changed_coverage = replace(
        coverage,
        items=coverage_items,
        releases=(
            *coverage.releases[:-1],
            replace(
                coverage.releases[-1],
                active=active,
                revisions=coverage_revisions,
            ),
        ),
    )
    monkeypatch.setattr(
        site_module,
        "load_research_questions",
        lambda actual_catalog: changed_questions,
    )
    monkeypatch.setattr(
        site_module,
        "load_research_coverage",
        lambda actual_catalog, actual_questions: changed_coverage,
    )


def test_pages_omit_only_the_zero_public_fire_group_from_the_taxonomy_outline(
    tmp_path: Path,
) -> None:
    outline = _TaxonomyOutline()
    outline.feed(_built_html(tmp_path))

    assert len(outline.group_depths) == 6
    assert len(outline.subtopic_depths) == 34
    assert min(outline.subtopic_depths) > min(outline.group_depths)


def test_pages_use_the_prerequisite_aware_public_order_and_taxonomy_counts(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    published = display_principles(catalog, published_only=True)
    html = _built_html(tmp_path)
    article_codes = re.findall(r'<article class="principle-card" id="([^"]+)"', html)
    group_count = len(catalog.taxonomy.groups)
    subtopic_count = sum(len(group.subtopics) for group in catalog.taxonomy.groups)

    assert article_codes == [item.code for item in published]
    positions = {item.id: index for index, item in enumerate(published)}
    for item in published:
        for prerequisite in item.prerequisites:
            if prerequisite in positions:
                assert positions[prerequisite] < positions[item.id]

    assert (
        f'<div><strong>{len(published)}</strong><span>公開項目</span></div>' in html
    )
    assert f'<div><strong>{group_count}</strong><span>大項目</span></div>' in html
    assert (
        f'<div><strong>{subtopic_count}</strong><span>小項目</span></div>' in html
    )
    assert "台帳化済み" not in html
    assert "公開セクション" not in html


def test_card_uses_public_code_and_edition_reference_with_legacy_anchor(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    item = display_principles(catalog, published_only=True)[0]
    edition = catalog.question_editions.editions[catalog.question_editions.current]
    reference = edition.reference(item.id)
    html = _built_html(tmp_path)

    assert f'id="{item.code}"' in html
    assert f'<p class="card-id">{item.code} / {reference}</p>' in html
    assert (
        f'id="{item.id}" data-legacy-anchor '
        f'data-canonical-fragment="{item.code}"' in html
    )
    assert f'href="#{item.code}" data-principle-link' in html
    assert f'<span data-print-position>問1</span> [{reference}]' in html
    card = _card_html(html, item.code)
    assert f'id="{item.id}" data-legacy-anchor' in card
    search_text = unescape(
        re.search(r'data-search="([^"]*)"', card).group(1)  # type: ignore[union-attr]
    )
    assert reference.casefold() in search_text


def test_every_central_identity_route_lands_on_a_card_or_explicit_notice(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    published = {
        item.id: item
        for item in display_principles(catalog, published_only=True)
    }
    html = _built_html(tmp_path)

    identifiers = _identity_identifiers(catalog, set(published))
    html_ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(html_ids) == len(set(html_ids))
    for identifier in identifiers:
        resolution = resolve_principle(catalog, identifier)
        escaped_identifier = escape(identifier)
        assert html.count(f'id="{escaped_identifier}"') == 1

        if resolution.is_split:
            opening = (
                f'<section class="migration-notice legacy-route" '
                f'id="{escaped_identifier}" data-split-migration>'
            )
            assert opening in html
            notice = html.split(opening, maxsplit=1)[1].split(
                "</section>", maxsplit=1
            )[0]
        else:
            item = resolution.require_one()
            if item.id in published:
                if identifier == item.code:
                    assert f'<article class="principle-card" id="{identifier}"' in html
                else:
                    assert (
                        f'id="{escaped_identifier}" data-legacy-anchor '
                        f'data-canonical-fragment="{item.code}"' in html
                    )
                notice = ""
            else:
                opening = (
                    f'<section class="migration-notice legacy-route" '
                    f'id="{escaped_identifier}" data-unpublished-route>'
                )
                assert opening in html
                notice = html.split(opening, maxsplit=1)[1].split(
                    "</section>", maxsplit=1
                )[0]
                assert "根拠確認中のため非公開" in notice

        for item in resolution.principles:
            if item.id in published:
                if resolution.is_split:
                    assert f'href="#{item.code}"' in notice
                card = _card_html(html, item.code)
                search_text = unescape(
                    re.search(r'data-search="([^"]*)"', card).group(1)  # type: ignore[union-attr]
                )
                assert identifier.casefold() in search_text
        pending_count = sum(
            item.id not in published for item in resolution.principles
        )
        if resolution.is_split and pending_count:
            assert (
                f"ほか{pending_count}件は根拠確認中のため非公開" in notice
            )

    private_split_target = next(
        item
        for item in catalog.principles
        if item.id == "S-K6-BRACED-FRAME-COLUMN-BRACE-CAPACITY-SUM"
    )
    assert private_split_target.code not in html
    assert escape(private_split_target.principle) not in html


def test_issued_active_card_that_becomes_private_keeps_only_generic_routes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    catalog = load_catalog()
    public_progress = load_public_progress()
    item = next(
        candidate
        for candidate in display_principles(catalog, published_only=True)
        if candidate.id not in public_progress.items
        and candidate.id
        not in {
            target
            for record in catalog.migration.retired.values()
            for target in record.targets
        }
    )
    private_item = replace(item, editorial_status="source_gap")
    issued_edition = catalog.question_editions.editions[
        catalog.question_editions.current
    ]
    future_assignments = {
        candidate.id: number
        for number, candidate in enumerate(
            (
                candidate
                for candidate in display_principles(catalog, published_only=True)
                if candidate.id != item.id
            ),
            start=1,
        )
    }
    future_edition = replace(
        issued_edition,
        id="K6-R3",
        status="current",
        assignments=future_assignments,
    )
    future_editions = {
        **catalog.question_editions.editions,
        issued_edition.id: replace(issued_edition, status="archived"),
        future_edition.id: future_edition,
    }
    changed_catalog = replace(
        catalog,
        principles=tuple(
            private_item if candidate.id == item.id else candidate
            for candidate in catalog.principles
        ),
        question_editions=replace(
            catalog.question_editions,
            current=future_edition.id,
            editions=future_editions,
        ),
    )
    registry = load_research_queries(catalog)
    release_id = f"steel-search-v{len(registry.releases) + 1}"
    changed_record = replace(
        registry.items[item.id],
        research_route_history=(
            *registry.items[item.id].research_route_history,
            release_id,
        ),
    )
    changed_items = {**registry.items, item.id: changed_record}
    revisions = dict(registry.releases[-1].revisions)
    route_history_lengths = {
        **registry.releases[-1].route_history_lengths,
        item.id: len(changed_record.research_route_history),
    }
    route_release = ResearchQueryRelease(
        id=release_id,
        revisions=revisions,
        route_history_lengths=route_history_lengths,
        content_sha256=_release_content_sha256(
            release_id,
            changed_items,
            revisions,
            route_history_lengths,
        ),
    )
    changed_registry = replace(
        registry,
        items=changed_items,
        releases=(*registry.releases, route_release),
    )
    monkeypatch.setattr(site_module, "load_catalog", lambda: changed_catalog)
    monkeypatch.setattr(
        site_module,
        "load_research_queries",
        lambda actual_catalog: changed_registry,
    )
    _patch_research_registries_for_catalog(monkeypatch, catalog, changed_catalog)

    html = _built_html(tmp_path)

    for identifier in (item.id, item.code, *catalog.identities.active[item.id].aliases):
        opening = (
            f'<section class="migration-notice legacy-route" '
            f'id="{escape(identifier)}" data-unpublished-route>'
        )
        assert html.count(opening) == 1
        notice_body = html.split(opening, maxsplit=1)[1].split(
            "</section>", maxsplit=1
        )[0]
        assert "対象項目は根拠確認中のため非公開" in notice_body
        assert item.code not in notice_body
        assert escape(item.principle) not in notice_body

    assert html.count(item.code) == 1
    assert escape(item.principle) not in html


def test_never_published_card_does_not_gain_public_routes_when_retired(
    tmp_path: Path,
    monkeypatch,
) -> None:
    catalog = load_catalog()
    issued_keys = {
        key
        for edition in catalog.question_editions.editions.values()
        for key in edition.assignments
    }
    item = next(
        candidate
        for candidate in catalog.principles
        if candidate.editorial_status != "source_checked"
        and candidate.id not in issued_keys
    )
    target = display_principles(catalog, published_only=True)[0]
    identity = catalog.identities.active[item.id]
    active_identities = dict(catalog.identities.active)
    del active_identities[item.id]
    retired_identities = {**catalog.identities.retired, item.id: identity}
    template_record = next(iter(catalog.migration.retired.values()))
    retirement = replace(
        template_record,
        operation="rename",
        targets=(target.id,),
        legacy_section=item.section_id,
    )
    changed_catalog = replace(
        catalog,
        principles=tuple(
            candidate for candidate in catalog.principles if candidate.id != item.id
        ),
        taxonomy=replace(
            catalog.taxonomy,
            assignments={
                key: subtopic
                for key, subtopic in catalog.taxonomy.assignments.items()
                if key != item.id
            },
        ),
        identities=replace(
            catalog.identities,
            active=active_identities,
            retired=retired_identities,
        ),
        migration=replace(
            catalog.migration,
            aliases={
                **catalog.migration.aliases,
                item.id: (target.id,),
                identity.code: (target.id,),
            },
            retired={**catalog.migration.retired, item.id: retirement},
        ),
    )
    monkeypatch.setattr(site_module, "load_catalog", lambda: changed_catalog)
    _patch_research_registries_for_catalog(monkeypatch, catalog, changed_catalog)

    html = _built_html(tmp_path)

    assert item.id not in html
    assert identity.code not in html
    assert escape(item.principle) not in html


def test_explicit_alias_of_an_issued_retired_identity_keeps_a_public_route(
    tmp_path: Path,
    monkeypatch,
) -> None:
    catalog = load_catalog()
    issued_keys = {
        key
        for edition in catalog.question_editions.editions.values()
        for key in edition.assignments
    }
    retired_key = next(
        key
        for key, record in catalog.migration.retired.items()
        if key in issued_keys and record.operation == "split"
    )
    identity = catalog.identities.retired[retired_key]
    public_alias = "structure.steel.issued-retired-test-alias"
    changed_identity = replace(
        identity,
        aliases=(*identity.aliases, public_alias),
    )
    changed_catalog = replace(
        catalog,
        identities=replace(
            catalog.identities,
            retired={
                **catalog.identities.retired,
                retired_key: changed_identity,
            },
        ),
    )
    monkeypatch.setattr(site_module, "load_catalog", lambda: changed_catalog)

    html = _built_html(tmp_path)

    assert html.count(f'id="{public_alias}"') == 1
    assert "data-split-migration" in html.split(
        f'id="{public_alias}"', maxsplit=1
    )[1].split("</section>", maxsplit=1)[0]


def test_historical_split_stays_an_index_after_its_leaves_converge(
    tmp_path: Path,
    monkeypatch,
) -> None:
    catalog = load_catalog()
    published = {
        item.id: item
        for item in display_principles(catalog, published_only=True)
    }
    active = {item.id: item for item in catalog.principles}
    split_key, split_record = next(
        (key, record)
        for key, record in catalog.migration.retired.items()
        if record.operation == "split"
        and len(record.targets) == 2
        and sum(target in published for target in record.targets) == 1
    )
    intermediate = next(
        target for target in split_record.targets if target not in published
    )
    leaf = next(target for target in split_record.targets if target in published)
    intermediate_identity = catalog.identities.active[intermediate]
    active_identities = dict(catalog.identities.active)
    del active_identities[intermediate]
    changed_catalog = replace(
        catalog,
        principles=tuple(
            item for item in catalog.principles if item.id != intermediate
        ),
        taxonomy=replace(
            catalog.taxonomy,
            assignments={
                key: subtopic
                for key, subtopic in catalog.taxonomy.assignments.items()
                if key != intermediate
            },
        ),
        identities=replace(
            catalog.identities,
            active=active_identities,
            retired={
                **catalog.identities.retired,
                intermediate: intermediate_identity,
            },
        ),
        migration=replace(
            catalog.migration,
            retired={
                **catalog.migration.retired,
                intermediate: replace(
                    split_record,
                    operation="rename",
                    targets=(leaf,),
                    legacy_section=active[intermediate].section_id,
                ),
            },
        ),
    )
    monkeypatch.setattr(site_module, "load_catalog", lambda: changed_catalog)
    _patch_research_registries_for_catalog(monkeypatch, catalog, changed_catalog)

    html = _built_html(tmp_path)
    opening = (
        f'<section class="migration-notice legacy-route" '
        f'id="{split_key}" data-split-migration>'
    )
    notice = html.split(opening, maxsplit=1)[1].split(
        "</section>", maxsplit=1
    )[0]

    assert "旧IDは複数の原理に分割されました" in notice
    assert f'href="#{published[leaf].code}"' in notice
    assert intermediate_identity.code not in html
    assert escape(active[intermediate].principle) not in html


def test_every_prior_section_fragment_lists_its_exact_taxonomy_destinations(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    published = {
        item.id: item
        for item in display_principles(catalog, published_only=True)
    }
    active = {item.id: item for item in catalog.principles}
    routes: dict[str, set[str]] = defaultdict(set)
    for edition in catalog.question_editions.editions.values():
        if edition.status != "archived":
            continue
        for legacy_key in edition.assignments:
            resolution = resolve_principle(catalog, legacy_key)
            legacy_section = (
                active[legacy_key].section_id
                if legacy_key in active
                else catalog.migration.retired[legacy_key].legacy_section
            )
            routes[legacy_section].update(resolution.keys)

    k6_00_merge_targets = {
        target
        for record in catalog.migration.retired.values()
        if record.operation == "merge" and record.legacy_section == "K6-00"
        for target in record.targets
    }
    k6_06_merge_targets = {
        target
        for record in catalog.migration.retired.values()
        if record.operation == "merge" and record.legacy_section == "K6-06"
        for target in record.targets
    }
    assert len(k6_00_merge_targets) == 2
    assert len(k6_06_merge_targets) == 2
    assert k6_00_merge_targets <= routes["K6-00"]
    assert k6_06_merge_targets <= routes["K6-06"]

    html = _built_html(tmp_path)
    for section_id, targets in routes.items():
        opening = (
            f'<section class="redistribution-index legacy-route" '
            f'id="section-{section_id}" data-section-migration>'
        )
        assert html.count(opening) == 1
        index = html.split(opening, maxsplit=1)[1].split(
            "</section>", maxsplit=1
        )[0]
        expected_subtopics = {
            catalog.taxonomy.assignments[target] for target in targets
        }
        actual_subtopics = set(
            re.findall(r'data-subtopic-destination="([^"]+)"', index)
        )
        assert actual_subtopics == expected_subtopics
        if any(target not in published for target in targets):
            assert "公開準備中" in index

    assert set(
        re.findall(
            r'id="section-(K6-[^"]+)" data-section-migration',
            html,
        )
    ) == set(routes) == {item.section_id for item in published.values()}
    assert len(routes) == 34
    assert "本試験知識（横断）の再分類先" in html.split(
        'id="section-K6-00"', maxsplit=1
    )[1].split("</section>", maxsplit=1)[0]


def test_legacy_route_notices_are_hidden_until_their_fragment_is_targeted(
    tmp_path: Path,
) -> None:
    html = _built_html(tmp_path)
    css = Path(site_module.__file__).with_name("static").joinpath("styles.css").read_text(
        encoding="utf-8"
    )

    assert 'class="migration-notice legacy-route"' in html
    assert 'class="redistribution-index legacy-route"' in html
    assert re.search(r"\.legacy-route\s*\{[^}]*display:\s*none", css, re.DOTALL)
    assert re.search(
        r"\.legacy-route:target\s*\{[^}]*display:\s*block",
        css,
        re.DOTALL,
    )


def test_published_cards_put_correct_answer_and_semantic_facets_in_disclosure(
    tmp_path: Path,
) -> None:
    catalog = load_catalog()
    published = display_principles(catalog, published_only=True)
    examples = {
        item_type: next(item for item in published if item.type == item_type)
        for item_type in ("principle", "rule", "identification")
    }
    html = _built_html(tmp_path)

    for item in examples.values():
        card = _card_html(html, item.code)
        facets = display_facets(catalog, item)
        assert '<details class="answer-disclosure" data-answer-disclosure>' in card
        assert "<summary>" in card
        disclosure_opening = card.split("<details", maxsplit=1)[1].split(
            ">", maxsplit=1
        )[0]
        assert " open" not in disclosure_opening
        assert (
            f'<p class="answer-key"><span>正解</span>'
            f"<strong>{item.question.correct}</strong></p>" in card
        )
        for facet in (facets.primary, facets.secondary, facets.tertiary):
            assert f"<dt>{escape(facet.label)}</dt>" in card
            if facet.values:
                assert all(escape(value) in card for value in facet.values)
            else:
                assert f"<dt>{escape(facet.label)}</dt><dd>—</dd>" in card


def test_pdf_provenance_is_visible_searchable_and_filterable(tmp_path: Path) -> None:
    catalog = load_catalog()
    item = next(
        item
        for item in display_principles(catalog, published_only=True)
        if item.source.question_codes
    )
    page_kinds = tuple(
        dict.fromkeys(catalog.audit.kind_for_page(page) for page in item.source.pages)
    )
    html = _built_html(tmp_path)
    card = _card_html(html, item.code)
    search_text = unescape(
        re.search(r'data-search="([^"]*)"', card).group(1)  # type: ignore[union-attr]
    )
    source_kinds = (*item.source.kinds, *page_kinds)

    assert all(kind in card.split(">", maxsplit=1)[0] for kind in source_kinds)
    for value in (
        item.code,
        item.id,
        *(f"P{page}" for page in item.source.pages),
        *item.source.question_codes,
        *page_kinds,
        item.type,
        item.editorial_status,
    ):
        assert value.casefold() in search_text
    assert "PDF " + "・".join(f"P{page}" for page in item.source.pages) in card
    assert "問題コード " + "・".join(item.source.question_codes) in card
    assert "ページ種別 " in card
    assert "主張根拠 " + item.verification.statement_source in card
    assert "説明 " + item.verification.explanation_completeness in card
    assert "条件 " + item.verification.conditions_completeness in card
    for kind in source_kinds:
        assert f'<option value="{kind}">' in html


def test_authoritative_source_is_visible_searchable_and_filterable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    catalog = load_catalog()
    item = display_principles(catalog, published_only=True)[0]
    authority = AuthoritativeSource(
        kind="law",
        title="建築基準法 & 施行令",
        locator="第1条第2項",
        url="https://example.com/law",
        supports=("statement", "conditions"),
    )
    changed_item = replace(
        item,
        source=replace(item.source, authoritative_sources=(authority,)),
    )
    changed_catalog = replace(
        catalog,
        principles=tuple(
            changed_item if candidate.id == item.id else candidate
            for candidate in catalog.principles
        ),
    )
    monkeypatch.setattr(site_module, "load_catalog", lambda: changed_catalog)

    html = _built_html(tmp_path)
    card = _card_html(html, item.code)
    search_text = unescape(
        re.search(r'data-search="([^"]*)"', card).group(1)  # type: ignore[union-attr]
    )

    card_opening = card.split(">", maxsplit=1)[0]
    for kind in ("pdf", "prior_question_table", "law"):
        assert kind in card_opening
    assert '<option value="law">法令</option>' in html
    assert 'aria-label="外部権威ソース"' in card
    assert 'href="https://example.com/law"' in card
    assert "建築基準法 &amp; 施行令" in card
    assert "第1条第2項" in card
    assert "対応：主張・条件" in card
    assert authority.title.casefold() in search_text
