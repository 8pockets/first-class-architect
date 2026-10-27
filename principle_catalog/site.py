"""Build a public, read-only, privacy-bounded static catalog."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import urljoin

import principle_catalog.catalog as catalog_module
from principle_catalog.figures import question_figure
from principle_catalog.practice import load_practice, render_practice
from principle_catalog.exam_coverage import ExamCoverageAudit, load_exam_coverage
from principle_catalog.catalog import (
    display_facets,
    display_principles,
    load_catalog,
    load_public_progress,
    resolve_principle,
    validate_public_progress,
)
from principle_catalog.models import (
    CardDisplayFacets,
    Catalog,
    Principle,
    PrincipleType,
    PublicProgress,
    QuestionEdition,
    ResearchCoverageRegistry,
    ResearchEvidence,
    ResearchIdentificationDetails,
    ResearchPrincipleDetails,
    ResearchQuestionRegistry,
    ResearchQuestionRevision,
    ResearchRuleDetails,
)
from principle_catalog.research import (
    ResearchQueryPair,
    ResearchQueryRecord,
    ResearchQueryRegistry,
    google_search_url,
    load_research_queries,
)
from principle_catalog.research_questions import (
    load_research_coverage,
    load_research_questions,
)


_OUTPUT_MARKER = ".principle-catalog-output"
_OUTPUT_MARKER_CONTENT = "first-class-architect-principle-catalog:v1\n"
_BASE_URL = re.compile(r"^https://[A-Za-z0-9.-]+/(?:[A-Za-z0-9._~-]+/)*$")
_TYPE_LABELS = {
    "principle": "原理",
    "rule": "規定",
    "identification": "識別",
}
_PROGRESS_LABELS: dict[PublicProgress, str] = {
    "unstarted": "未学習",
    "learning": "学習中",
    "reviewing": "復習中",
    "retained_14d": "14日保持",
}
_PAGE_KIND_LABELS = {
    "chapter_cover": "章扉",
    "prior_question_table": "本試験知識表",
    "teaching_material": "教材本文",
    "worked_examples": "例題・解説",
}
_SOURCE_KIND_LABELS = {
    "pdf": "PDF",
    "law": "法令",
    "notification": "告示",
    "jis": "JIS",
    "aij": "日本建築学会",
    "government_spec": "官庁仕様",
    "government_research": "公的研究機関",
    "professional_body": "専門団体",
    "local_government": "自治体技術資料",
    "official_exam": "公式試験資料",
    "study_material": "教材・補完範囲",
    **_PAGE_KIND_LABELS,
}
_SUPPORT_LABELS = {
    "statement": "主張",
    "explanation": "説明",
    "conditions": "条件",
}
_RESEARCH_STATUS_LABELS = {
    "draft": "未監査",
    "source_gap": "根拠確認待ち",
    "source_checked": "確認済み",
}
_RESEARCH_QUESTION_STATE_LABELS = {
    "provisional_answer": "暫定正解あり",
    "pending": "判定保留",
}
_RESEARCH_COVERAGE_LABELS = {
    1: ("core", "候補層：骨格"),
    2: ("standard", "候補層：標準"),
    3: ("advanced", "候補層：発展"),
}
_RESEARCH_EVIDENCE_SUPPORT_LABELS = {
    "question": "問題",
    "answer": "暫定正解",
    "details": "内容",
}


def _asset_text(name: str) -> str:
    path = Path(__file__).with_name("static") / name
    return path.read_text(encoding="utf-8")


def _versioned_asset_url(base_url: str, name: str) -> str:
    version = hashlib.sha256(_asset_text(name).encode("utf-8")).hexdigest()[:12]
    return urljoin(base_url, f"assets/{name}") + f"?v={version}"


def _stylesheet_url(base_url: str) -> str:
    return _versioned_asset_url(base_url, "styles.css")


def _page_kinds(catalog: Catalog, item: Principle) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(catalog.audit.kind_for_page(page) for page in item.source.pages)
    )


def _source_filter_kinds(catalog: Catalog, item: Principle) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*item.source.kinds, *_page_kinds(catalog, item))))


def _source_label(catalog: Catalog, item: Principle) -> str:
    pages = "・".join(f"P{page}" for page in item.source.pages)
    parts = [f"PDF {pages}"] if pages else []
    if item.source.question_codes:
        parts.append(f"問題コード {'・'.join(item.source.question_codes)}")
    kinds = "・".join(
        _PAGE_KIND_LABELS.get(kind, kind) for kind in _page_kinds(catalog, item)
    )
    if kinds:
        parts.append(f"ページ種別 {kinds}")
    return " / ".join(parts)


def _authoritative_sources(item: Principle) -> str:
    if not item.source.authoritative_sources:
        return ""
    rendered: list[str] = []
    for source in item.source.authoritative_sources:
        title = escape(source.title)
        if source.url:
            title = (
                f'<a class="authority-link" href="{escape(source.url)}" '
                f'rel="noopener noreferrer">{title}</a>'
            )
        supports = "・".join(_SUPPORT_LABELS[support] for support in source.supports)
        rendered.append(
            f"<li>{escape(_SOURCE_KIND_LABELS.get(source.kind, source.kind))}："
            f"{title} / {escape(source.locator)} / 対応：{escape(supports)}</li>"
        )
    return (
        '<ul class="authority-sources" aria-label="外部権威ソース">'
        + "".join(rendered)
        + "</ul>"
    )


def _binary_choices(item: Principle) -> str:
    if item.question is None:
        raise ValueError(f"published principle has no confirmation question: {item.id}")
    answer_id = f"answer-{item.code}"
    return "".join(
        f'<li><button type="button" class="choice-button" data-answer-choice="{label}" '
        f'aria-controls="{escape(answer_id)}" aria-expanded="false">'
        f'<span class="choice-label">{label}</span>'
        f'<span class="choice-text">{escape(text)}</span></button></li>'
        for label, text in (
            ("A", item.question.choice_a),
            ("B", item.question.choice_b),
        )
    )


def _facet_value(values: tuple[str, ...]) -> str:
    if not values:
        return "—"
    if len(values) == 1:
        return escape(values[0])
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def _facet_list(facets: CardDisplayFacets) -> str:
    return "".join(
        f"<div><dt>{escape(facet.label)}</dt><dd>{_facet_value(facet.values)}</dd></div>"
        for facet in (facets.primary, facets.secondary, facets.tertiary)
    )


def _action_icon(name: str) -> str:
    shapes = {
        "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
        "eye-off": '<path d="m3 3 18 18M10.6 5.1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.1 3.9M6.2 6.2A21 21 0 0 0 2 12s3.5 7 10 7a13 13 0 0 0 5.8-1.8M10 10a3 3 0 0 0 4 4"/>',
        "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
        "retry": '<path d="M3 10a9 9 0 1 1 1.6 7M3 4v6h6"/>',
    }
    return (
        f'<svg class="action-icon" data-icon="{name}" viewBox="0 0 24 24" '
        'width="18" height="18" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">{shapes[name]}</svg>'
    )


def _explanation_search_action(
    item: Principle,
    queries: ResearchQueryPair | None,
    *,
    neutral: str | None = None,
) -> str:
    if queries is None:
        return ""
    accessible_name = (
        f"{neutral or item.principle}：分かりやすい解説をGoogleで検索（別タブ）"
    )
    return f"""
<div class="explanation-search-action">
  <a class="explanation-search-button" href="{escape(google_search_url(queries.explanation))}" target="_blank"
    rel="external nofollow noopener noreferrer" referrerpolicy="no-referrer"
    aria-label="{escape(accessible_name)}"
    data-research-search="explanation">Googleで解説を探す</a>
</div>""".strip()


def _prerequisite_links(catalog: Catalog, item: Principle) -> str:
    published = {
        candidate.id: candidate for candidate in catalog.principles
        if candidate.editorial_status == "source_checked"
    }
    links = [
        f'<li><a href="#{escape(published[key].code)}" '
        f'data-prerequisite-link="{escape(key)}">{escape(published[key].principle)}</a></li>'
        for key in item.prerequisites if key in published
    ]
    if not links:
        return ""
    return (
        '<aside class="prerequisite-links" aria-label="理解の土台になる論点">'
        '<h5>つまずいたら、前提を確かめる</h5><ul>'
        + "".join(links) + '</ul></aside>'
    )


def _card(
    catalog: Catalog,
    item: Principle,
    progress: PublicProgress,
    print_position: int,
    question_reference: str,
    legacy_anchor_aliases: tuple[str, ...],
    legacy_search_aliases: tuple[str, ...],
    facets: CardDisplayFacets,
    taxonomy_context: tuple[str, ...],
    research_queries: ResearchQueryPair | None,
    practice_html: str = "",
) -> str:
    if item.question is None:
        raise ValueError(f"published principle has no confirmation question: {item.id}")
    coverage = catalog_module.coverage_assignment(catalog, item)
    coverage_tier = catalog.coverage.tiers[coverage.tier]
    section_id = catalog.taxonomy.assignments[item.id]
    group = next(
        group for group in catalog.taxonomy.groups
        if any(subtopic.id == section_id for subtopic in group.subtopics)
    )
    # Numbering/taxonomy/source metadata can change without regrading history.
    # A changed question, answer, or taught content starts a separate revision.
    revision = hashlib.sha256(json.dumps({
        "prompt": item.question.prompt,
        "choices": [item.question.choice_a, item.question.choice_b],
        "correct": item.question.correct,
        "figure": item.question.figure,
        "content": [facets.primary.values, facets.secondary.values, facets.tertiary.values],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    page_kinds = _page_kinds(catalog, item)
    source_kinds = _source_filter_kinds(catalog, item)
    authoritative_search = tuple(
        value
        for source in item.source.authoritative_sources
        for value in (
            source.kind,
            _SOURCE_KIND_LABELS.get(source.kind, source.kind),
            source.title,
            source.locator,
            source.url or "",
            *source.supports,
        )
    )
    search_text = " ".join(
        [
            item.code,
            item.id,
            *legacy_search_aliases,
            question_reference,
            item.principle,
            item.question.prompt,
            item.question.choice_a,
            item.question.choice_b,
            *(
                value
                for facet in (facets.primary, facets.secondary, facets.tertiary)
                for value in facet.values
            ),
            *(
                facet.label
                for facet in (facets.primary, facets.secondary, facets.tertiary)
            ),
            *taxonomy_context,
            *(f"P{page}" for page in item.source.pages),
            *(str(page) for page in item.source.pages),
            *item.source.question_codes,
            *page_kinds,
            *(_PAGE_KIND_LABELS.get(kind, kind) for kind in page_kinds),
            *item.source.kinds,
            *(_SOURCE_KIND_LABELS.get(kind, kind) for kind in item.source.kinds),
            *authoritative_search,
            item.type,
            _TYPE_LABELS[item.type],
            item.editorial_status,
            progress,
            _PROGRESS_LABELS[progress],
            item.verification.statement_source,
            item.verification.explanation_completeness,
            item.verification.conditions_completeness,
            str(coverage.tier),
            coverage_tier.slug,
            coverage_tier.label,
        ]
    )
    legacy_anchors = "".join(
        f'<span id="{escape(alias)}" data-legacy-anchor '
        f'data-canonical-fragment="{escape(item.code)}" aria-hidden="true"></span>'
        for alias in legacy_anchor_aliases
        if alias != item.code
    )
    return f"""
<article class="principle-card" id="{escape(item.code)}"
  data-study-id="{escape(item.id)}"
  data-question-revision="{revision}"
  data-correct-choice="{item.question.correct}"
  data-type="{escape(item.type)}"
  data-section="{escape(section_id)}"
  data-section-title="{escape(taxonomy_context[-1])}"
  data-group="{escape(group.id)}"
  data-group-title="{escape(group.title)}"
  data-introduction-order="{coverage.introduction_order}"
  data-prerequisites="{escape(' '.join(item.prerequisites))}"
  data-progress="{escape(progress)}"
  data-source-kind="{escape(' '.join(source_kinds))}"
  data-coverage-tier="{coverage.tier}"
  data-coverage-label="{escape(coverage_tier.label)}"
  data-search="{escape(search_text.casefold())}">
  {legacy_anchors}
  <header class="card-header">
    <div class="badge-row">
      <span class="coverage-badge coverage-{escape(coverage_tier.slug)}">{escape(coverage_tier.label)}</span>
    </div>
    <p class="card-id">{escape(question_reference)}</p>
    <h3>{escape(taxonomy_context[-1])}</h3>
    <button class="favorite-button" type="button" data-favorite-toggle aria-pressed="false" aria-label="お気に入り：{escape(question_reference)}" title="お気に入りに追加" hidden>☆</button>
  </header>
  <div class="practice-question">
    <p class="print-question-number" aria-hidden="true"><span data-print-position>問{print_position}</span> [{escape(question_reference)}]</p>
    <p class="practice-question-label">確認問題（自作・2択）</p>
    <p class="practice-question-text">{escape(item.question.prompt)}</p>
    {question_figure(item.question.figure)}
    <ul class="binary-choices">{_binary_choices(item)}</ul>
  </div>
  <div class="answer-feedback" data-answer-result role="status" aria-live="polite">未回答</div>
  <div class="card-disclosures">
  <button class="answer-retry card-action" type="button" data-answer-retry title="もう一度解く" aria-label="もう一度解く：{escape(question_reference)}" hidden>{_action_icon('retry')}</button>
  <details id="answer-{escape(item.code)}" class="answer-disclosure" data-answer-disclosure>
    <summary class="card-action" title="正解と解説を開閉">
      <span class="disclosure-label-closed">{_action_icon('eye')}<span class="visually-hidden">正解と解説を見る</span><span class="visually-hidden">：{escape(question_reference)}</span></span>
      <span class="disclosure-label-open">{_action_icon('eye-off')}<span class="visually-hidden">正解と解説を閉じる</span><span class="visually-hidden">：{escape(question_reference)}</span></span>
    </summary>
    <div class="answer-content">
      <h4>{escape(item.principle)}</h4>
      <p class="answer-key"><span>正解</span><strong>{escape(item.question.correct)}</strong></p>
      <dl class="three-point">{_facet_list(facets)}</dl>
      <p class="card-id">{escape(item.code)}</p>
      {_authoritative_sources(item)}
      {_explanation_search_action(item, research_queries, neutral=question_reference)}
      {_prerequisite_links(catalog, item)}
      {practice_html}
    </div>
  </details>
  <details class="card-tools">
    <summary class="card-action" title="補助情報（回答状況・種類・履歴・出典）">{_action_icon('info')}<span class="visually-hidden">補助情報：{escape(question_reference)}</span></summary>
    <div class="card-tools-content">
    <p class="answer-status-details" data-answer-status-details>未回答</p>
    <p class="card-content-type">内容の種類 <span class="type-badge type-{escape(item.type)}">{_TYPE_LABELS[item.type]}</span></p>
    <details class="answer-history" data-answer-history>
      <summary>この問題の回答履歴</summary>
      <ul data-answer-history-list><li>この端末にはまだ履歴がありません。</li></ul>
    </details>
    <footer class="card-source">
      <details class="source-provenance">
        <summary>出典・確認状況</summary>
        <span>{escape(_source_label(catalog, item))}</span>
        <span>主張根拠 {escape(item.verification.statement_source)} / 説明 {escape(item.verification.explanation_completeness)} / 条件 {escape(item.verification.conditions_completeness)}</span>
      </details>
      <a href="#{escape(item.code)}" data-principle-link aria-label="{escape(question_reference)}への固定リンク">#</a>
    </footer>
    </div>
  </details>
  </div>
</article>""".strip()


def _taxonomy_nav(catalog: Catalog, items: tuple[Principle, ...]) -> str:
    taxonomy = catalog.taxonomy
    visible_keys = {item.id for item in items}
    links: list[str] = []
    for group in sorted(taxonomy.groups, key=lambda candidate: candidate.order):
        subtopic_ids = {subtopic.id for subtopic in group.subtopics}
        count = sum(
            key in visible_keys and subtopic_id in subtopic_ids
            for key, subtopic_id in taxonomy.assignments.items()
        )
        if count == 0:
            continue
        links.append(
            f'<a href="#group-{escape(group.id)}">'
            f'{escape(group.title)}<span data-total-count="{count}" '
            f'data-count-for="group-{escape(group.id)}">{count}</span></a>'
        )
    return "".join(links)


def _taxonomy_sections(
    catalog: Catalog,
    items: tuple[Principle, ...],
    progress: dict[str, PublicProgress],
    edition: QuestionEdition,
    legacy_anchor_aliases: dict[str, tuple[str, ...]],
    legacy_search_aliases: dict[str, tuple[str, ...]],
    research_queries: ResearchQueryRegistry,
    practice_variants: dict | None = None,
) -> str:
    by_subtopic: dict[str, list[Principle]] = {}
    for item in items:
        by_subtopic.setdefault(catalog.taxonomy.assignments[item.id], []).append(item)

    rendered_groups: list[str] = []
    for group in sorted(catalog.taxonomy.groups, key=lambda candidate: candidate.order):
        subtopic_ids = {subtopic.id for subtopic in group.subtopics}
        rendered_subtopics: list[str] = []
        group_count = 0
        for subtopic in sorted(group.subtopics, key=lambda candidate: candidate.order):
            subtopic_items = by_subtopic.get(subtopic.id, [])
            group_count += len(subtopic_items)
            cards = "\n".join(
                _card(
                    catalog,
                    item,
                    progress.get(item.id, "unstarted"),
                    edition.assignments[item.id],
                    edition.reference(item.id),
                    legacy_anchor_aliases[item.id],
                    legacy_search_aliases[item.id],
                    display_facets(catalog, item),
                    (group.id, group.title, subtopic.id, subtopic.title),
                    (
                        research_queries.items[item.id].current
                        if item.id in research_queries.items
                        else None
                    ),
                    "".join(render_practice(variant) for variant in (practice_variants or {}).get(item.id, ())),
                )
                for item in subtopic_items
            )
            rendered_subtopics.append(
                f"""
<section class="catalog-section" id="subtopic-{escape(subtopic.id)}"
  data-catalog-section data-taxonomy-subtopic="{escape(subtopic.id)}">
  <div class="section-heading">
    <p>{escape(subtopic.id)}</p>
    <h3>{escape(subtopic.title)}</h3>
    <span data-total-count="{len(subtopic_items)}" data-count-for="subtopic-{escape(subtopic.id)}">{len(subtopic_items)}件</span>
  </div>
  <div class="card-grid">{cards}</div>
</section>""".strip()
            )
        pending_count = sum(
            item.editorial_status != "source_checked"
            and catalog.taxonomy.assignments[item.id] in subtopic_ids
            for item in catalog.principles
        )
        coverage_notice = (
            f'<p class="coverage-gap-notice">{escape(group.title)}：'
            f"根拠確認待ち{pending_count}件</p>"
            if group_count == 0 and pending_count
            else ""
        )
        if group_count == 0:
            if coverage_notice:
                rendered_groups.append(coverage_notice)
            continue
        rendered_subtopics_html = "\n".join(rendered_subtopics)
        rendered_groups.append(
            coverage_notice
            +
            f"""
<section class="catalog-group" id="group-{escape(group.id)}"
  data-catalog-group data-taxonomy-group="{escape(group.id)}">
  <div class="section-heading">
    <p>{escape(group.id)}</p>
    <h2>{escape(group.title)}</h2>
    <span data-total-count="{group_count}" data-count-for="group-{escape(group.id)}">{group_count}件</span>
  </div>
  {rendered_subtopics_html}
</section>""".strip()
        )
    return "\n".join(rendered_groups)


def _identity_identifiers(
    catalog: Catalog,
    published_keys: set[str],
) -> tuple[str, ...]:
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
    return tuple(sorted(identifiers))


def _migration_notice(
    identifier: str,
    targets: tuple[Principle, ...],
    published_keys: set[str],
    *,
    is_split: bool,
) -> str:
    target_items: list[str] = []
    pending_count = 0
    for item in targets:
        if item.id in published_keys:
            label = f"{item.code} — {item.principle}"
            target_items.append(
                f'<li><a href="#{escape(item.code)}">{escape(label)}</a></li>'
            )
        else:
            pending_count += 1
    if pending_count:
        pending_message = (
            f"ほか{pending_count}件は根拠確認中のため非公開"
            if is_split
            else "対象項目は根拠確認中のため非公開"
        )
        target_items.append(f'<li class="pending-targets">{pending_message}</li>')
    data_attribute = "data-split-migration" if is_split else "data-unpublished-route"
    heading = (
        "旧IDは複数の原理に分割されました"
        if is_split
        else "この項目は現在非公開です"
    )
    identifier_label = (
        f"<p>識別子：<code>{escape(identifier)}</code></p>" if is_split else ""
    )
    return f"""
<section class="migration-notice legacy-route" id="{escape(identifier)}" {data_attribute}>
  {identifier_label}
  <h2>{heading}</h2>
  <ul>{"".join(target_items)}</ul>
</section>""".strip()


def _identity_routes(
    catalog: Catalog,
) -> tuple[
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
    str,
]:
    published_keys = {
        item.id
        for item in display_principles(catalog, published_only=True)
    }
    anchor_aliases: dict[str, set[str]] = {
        item.id: set() for item in catalog.principles
    }
    search_aliases: dict[str, set[str]] = {
        item.id: set() for item in catalog.principles
    }
    notices: list[str] = []
    for identifier in _identity_identifiers(catalog, published_keys):
        resolution = resolve_principle(catalog, identifier)
        for item in resolution.principles:
            if item.id in published_keys:
                search_aliases[item.id].add(identifier)
        if resolution.is_split:
            notices.append(
                _migration_notice(
                    identifier,
                    resolution.principles,
                    published_keys,
                    is_split=True,
                )
            )
            continue
        item = resolution.require_one()
        if item.id not in published_keys:
            notices.append(
                _migration_notice(
                    identifier,
                    resolution.principles,
                    published_keys,
                    is_split=False,
                )
            )
        elif identifier != item.code:
            anchor_aliases[item.id].add(identifier)
    return (
        {key: tuple(sorted(values)) for key, values in anchor_aliases.items()},
        {key: tuple(sorted(values)) for key, values in search_aliases.items()},
        "\n".join(notices),
    )


def _legacy_section_routes(
    catalog: Catalog,
    published: tuple[Principle, ...],
) -> str:
    active_by_key = {item.id: item for item in catalog.principles}
    published_keys = {item.id for item in published}
    targets_by_section: dict[str, set[str]] = {}
    for edition in catalog.question_editions.editions.values():
        if edition.status != "archived":
            continue
        for legacy_key in edition.assignments:
            resolution = resolve_principle(catalog, legacy_key)
            legacy_section = (
                active_by_key[legacy_key].section_id
                if legacy_key in active_by_key
                else catalog.migration.retired[legacy_key].legacy_section
            )
            targets_by_section.setdefault(legacy_section, set()).update(
                resolution.keys
            )

    routes: list[str] = []
    for section_id in sorted(targets_by_section):
        targets = targets_by_section[section_id]
        by_subtopic: dict[str, list[Principle]] = {}
        for key in targets:
            item = active_by_key[key]
            subtopic_id = catalog.taxonomy.assignments[key]
            by_subtopic.setdefault(subtopic_id, []).append(item)
        destinations: list[str] = []
        for group in sorted(catalog.taxonomy.groups, key=lambda candidate: candidate.order):
            for subtopic in sorted(group.subtopics, key=lambda candidate: candidate.order):
                items = by_subtopic.get(subtopic.id)
                if not items:
                    continue
                public_count = sum(item.id in published_keys for item in items)
                pending_count = len(items) - public_count
                label = f"{group.title} / {subtopic.title}"
                if public_count:
                    destination = (
                        f'<a href="#subtopic-{escape(subtopic.id)}">'
                        f"{escape(label)}</a>"
                    )
                else:
                    destination = escape(label)
                status_parts = []
                if public_count:
                    status_parts.append(f"公開{public_count}件")
                if pending_count:
                    status_parts.append(f"公開準備中{pending_count}件")
                destinations.append(
                    f'<li data-subtopic-destination="{escape(subtopic.id)}">'
                    f"{destination}<span>{' / '.join(status_parts)}</span></li>"
                )
        heading = (
            "本試験知識（横断）の再分類先"
            if section_id == "K6-00"
            else f"{section_id}の再分類先"
        )
        routes.append(
            f"""
<section class="redistribution-index legacy-route" id="section-{escape(section_id)}" data-section-migration>
  <p>旧セクション：{escape(section_id)}</p>
  <h2>{escape(heading)}</h2>
  <p>旧セクションの項目は、判断に使う主題ごとの小項目へ再分類しました。</p>
  <ul>{"".join(destinations)}</ul>
</section>""".strip()
        )
    return "\n".join(routes)


def _source_kind_options(catalog: Catalog, items: tuple[Principle, ...]) -> str:
    present = {
        kind
        for item in items
        for kind in _source_filter_kinds(catalog, item)
    }
    ordered = (
        "pdf",
        "law",
        "notification",
        "jis",
        "aij",
        "government_spec",
        *catalog.audit.page_kinds,
    )
    return "".join(
        f'<option value="{escape(kind)}">{escape(_SOURCE_KIND_LABELS.get(kind, kind))}</option>'
        for kind in dict.fromkeys(ordered)
        if kind in present
    )


def _research_detail_rows(question: ResearchQuestionRevision) -> str:
    details = question.details
    if isinstance(details, ResearchPrincipleDetails):
        rows = (
            ("暫定結論", (details.conclusion,)),
            ("暫定理由", (details.reason,)),
            ("暫定条件", details.conditions),
        )
    elif isinstance(details, ResearchRuleDetails):
        rows = (
            ("暫定規定", (details.rule,)),
            ("暫定適用範囲", details.applicability),
            ("暫定数値・例外", details.numbers_exceptions),
        )
    elif isinstance(details, ResearchIdentificationDetails):
        rows = (
            ("暫定定義", (details.definition,)),
            ("暫定識別条件", details.distinguishing_conditions),
            ("暫定混同注意", details.confusable_points),
        )
    else:
        raise TypeError(f"unsupported research details: {type(details).__name__}")
    return "".join(
        f"<div><dt>{label}</dt><dd>{_facet_value(values)}</dd></div>"
        for label, values in rows
    )


def _research_evidence_item(evidence: ResearchEvidence) -> str:
    supports = "・".join(
        _RESEARCH_EVIDENCE_SUPPORT_LABELS[support]
        for support in evidence.supports
    )
    if evidence.kind == "ledger":
        description = "既存台帳"
    elif evidence.kind == "external":
        description = "外部資料確認"
    else:
        description = "Codex補足（正答根拠外）"
    return f"<li><span>{description}</span><small>対応：{escape(supports)}</small></li>"


def _research_card(
    item: Principle,
    queries: ResearchQueryPair,
    question: ResearchQuestionRevision,
    question_type: PrincipleType,
    coverage_tier: int,
) -> str:
    tier_slug, tier_label = _RESEARCH_COVERAGE_LABELS[coverage_tier]
    answer_id = f"research-answer-{item.code}"
    choices = "".join(
        f'<li><button type="button" class="research-choice-button" '
        f'data-research-answer-choice aria-controls="{escape(answer_id)}" '
        f'aria-expanded="false">'
        f'<span class="research-choice-label">{label}</span>'
        f'<span class="research-choice-text">{escape(text)}</span></button></li>'
        for label, text in (("A", question.choice_a), ("B", question.choice_b))
    )
    if question.answer is None:
        answer = '<p class="research-answer-pending">暫定正解は保留中です。</p>'
        disclosure_label = "判定保留の内容を見る"
        disclosure_close_label = "判定保留の内容を閉じる"
    else:
        answer_text = question.choice_a if question.answer == "A" else question.choice_b
        answer = (
            '<p class="research-answer-key"><span>暫定正解</span>'
            f'<span class="research-answer-label">{question.answer}</span>'
            f'<strong>{escape(answer_text)}</strong></p>'
        )
        disclosure_label = "暫定正解と内容を見る"
        disclosure_close_label = "暫定正解と内容を閉じる"
    evidence = "".join(_research_evidence_item(item) for item in question.evidence)
    return f"""
<article class="research-card" id="{escape(item.code)}"
  data-editorial-status="{escape(item.editorial_status)}"
  data-research-coverage-tier="{coverage_tier}">
  <header class="research-card-header">
    <div class="badge-row">
      <span class="type-badge type-{escape(question_type)}">{_TYPE_LABELS[question_type]}</span>
      <span class="research-status-badge">{escape(_RESEARCH_STATUS_LABELS[item.editorial_status])}</span>
      <span class="research-question-state state-{escape(question.state)}">{_RESEARCH_QUESTION_STATE_LABELS[question.state]}</span>
      <span class="research-tier-badge tier-{tier_slug}">{tier_label}</span>
    </div>
    <p class="card-id">{escape(item.code)}</p>
    <h3>{escape(item.principle)}</h3>
  </header>
  <p class="research-card-warning"><strong>未確認：</strong>誤り・欠落を含む可能性があります。</p>
  <section class="research-question" aria-label="暫定確認問題">
    <p>{escape(question.prompt)}</p>
    <ol class="research-binary-choices">{choices}</ol>
  </section>
  <details id="{escape(answer_id)}" class="research-answer-disclosure" data-research-answer-disclosure>
    <summary>
      <span class="disclosure-label-closed">{disclosure_label}<span class="visually-hidden">：{escape(item.principle)}</span></span>
      <span class="disclosure-label-open">{disclosure_close_label}<span class="visually-hidden">：{escape(item.principle)}</span></span>
    </summary>
    {answer}
    <dl class="provisional-three-point">{_research_detail_rows(question)}</dl>
  </details>
  <aside class="research-evidence" aria-label="根拠の状態">
    <h4>根拠の状態</h4>
    <ul>{evidence}</ul>
  </aside>
  {_explanation_search_action(item, queries)}
  <footer class="card-source research-card-source">
    <a href="#{escape(item.code)}" data-principle-link aria-label="{escape(item.principle)}への固定リンク">#</a>
  </footer>
</article>""".strip()


def _research_transition(
    item: Principle,
    publication: ResearchQueryRecord,
    base_url: str,
) -> str:
    return f"""
<section class="research-transition legacy-route" id="{escape(publication.code)}"
  data-research-transition>
  <p>この調査項目は根拠確認を完了しました。</p>
  <h2>{escape(item.principle)}</h2>
  <a href="{escape(urljoin(base_url, f'./#{item.code}'))}">確認済みの学習カードを見る</a>
</section>""".strip()


def _research_migration_transition(
    catalog: Catalog,
    key: str,
    publication: ResearchQueryRecord,
    registry: ResearchQueryRegistry,
    base_url: str,
) -> str:
    resolution = resolve_principle(catalog, key)
    if resolution.is_split:
        operation = "split"
    elif resolution.migration is not None:
        operation = resolution.migration.operation
    else:
        operation = "rename"
    visible_targets: list[str] = []
    unpublished_count = 0
    for target in resolution.principles:
        if target.editorial_status == "source_checked":
            target_url = urljoin(base_url, f"./#{target.code}")
            destination = "確認済みの学習カード"
        elif (
            target.id in registry.items
            and registry.items[target.id].has_research_route
        ):
            target_url = f"#{registry.items[target.id].code}"
            destination = "暫定調査カード"
        else:
            unpublished_count += 1
            continue
        visible_targets.append(
            f'<li><a href="{escape(target_url)}">{escape(target.principle)}</a>'
            f"<span>{destination}</span></li>"
        )

    if operation == "split":
        message = "この調査項目は複数の項目へ分割されました。"
    elif operation == "merge":
        message = "この調査項目は別の項目へ統合されました。"
    else:
        message = "この調査項目は別の項目へ移行しました。"
    destinations = (
        f'<ul class="research-migration-targets">{"".join(visible_targets)}</ul>'
        if visible_targets
        else ""
    )
    unpublished = ""
    if unpublished_count:
        label = (
            f"ほか{unpublished_count}件の移行先は根拠確認中のため未公開です。"
            if visible_targets
            else "移行先は根拠確認中のため未公開です。"
        )
        unpublished = (
            f'<p data-unpublished-research-targets="{unpublished_count}">'
            f"{label}</p>"
        )
    return f"""
<section class="research-transition legacy-route" id="{escape(publication.code)}" data-research-migration="{operation}">
  <p>{message}</p>
  <h2>調査URLの移行先</h2>
  {destinations}
  {unpublished}
</section>""".strip()


def _research_active_keys(
    registry: ResearchQuestionRegistry | ResearchCoverageRegistry,
) -> tuple[str, ...]:
    return tuple(registry.active_keys)


def _research_sections(
    catalog: Catalog,
    queries: ResearchQueryRegistry,
    questions: ResearchQuestionRegistry,
    candidate_coverage: ResearchCoverageRegistry,
    base_url: str,
) -> tuple[str, str, tuple[Principle, ...]]:
    by_key = {item.id: item for item in catalog.principles}
    active_keys = set(_research_active_keys(questions)) & set(
        _research_active_keys(candidate_coverage)
    )
    visible = tuple(
        item
        for item in display_principles(catalog)
        if item.id in active_keys
        and item.id in queries.items
        and queries.items[item.id].has_research_route
        and item.editorial_status != "source_checked"
    )
    by_subtopic: dict[str, list[Principle]] = {}
    for item in visible:
        by_subtopic.setdefault(catalog.taxonomy.assignments[item.id], []).append(item)

    nav: list[str] = []
    sections: list[str] = []
    for group in sorted(catalog.taxonomy.groups, key=lambda candidate: candidate.order):
        for subtopic in sorted(group.subtopics, key=lambda candidate: candidate.order):
            items = by_subtopic.get(subtopic.id, [])
            if not items:
                continue
            nav.append(
                f'<a href="#research-{escape(subtopic.id)}" '
                f'data-research-nav-target="research-{escape(subtopic.id)}">'
                f"{escape(subtopic.title)}<span>{len(items)}</span></a>"
            )
            cards = "\n".join(
                _research_card(
                    item,
                    queries.items[item.id].current,
                    questions.items[item.id].current,
                    questions.items[item.id].type,
                    candidate_coverage.items[item.id].current.tier,
                )
                for item in items
            )
            sections.append(
                f"""
<section class="research-section" id="research-{escape(subtopic.id)}" data-research-section>
  <div class="section-heading">
    <p>{escape(subtopic.id)}</p>
    <h2>{escape(subtopic.title)}</h2>
    <span>{len(items)}件</span>
  </div>
  <div class="research-card-grid">{cards}</div>
</section>""".strip()
            )
    transitions: list[str] = []
    for key, publication in queries.items.items():
        if not publication.has_research_route:
            continue
        item = by_key.get(key)
        if item is not None and item.editorial_status == "source_checked":
            transitions.append(_research_transition(item, publication, base_url))
        elif item is None:
            transitions.append(
                _research_migration_transition(
                    catalog,
                    key,
                    publication,
                    queries,
                    base_url,
                )
            )
    return "".join(nav), "\n".join((*sections, *transitions)), visible


def _research_page(
    base_url: str,
    catalog: Catalog,
    queries: ResearchQueryRegistry,
    questions: ResearchQuestionRegistry,
    candidate_coverage: ResearchCoverageRegistry,
) -> str:
    nav, sections, visible = _research_sections(
        catalog,
        queries,
        questions,
        candidate_coverage,
        base_url,
    )
    visible_count = len(visible)
    answerable_count = sum(
        questions.items[item.id].current.state == "provisional_answer"
        for item in visible
    )
    pending_count = visible_count - answerable_count
    tier_counts = Counter(
        candidate_coverage.items[item.id].current.tier for item in visible
    )
    canonical_url = urljoin(base_url, "research/")
    stylesheet_url = _stylesheet_url(base_url)
    script_url = urljoin(base_url, "assets/research.js")
    home_url = urljoin(base_url, "./")
    if not visible:
        return f'''<!doctype html>
<html lang="ja" class="research-document">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,follow">
  <title>確認済みカードへの移行案内 — 鉄骨構造 原理台帳</title>
  <link rel="canonical" href="{escape(canonical_url)}">
  <link rel="stylesheet" href="{escape(stylesheet_url)}">
</head>
<body class="research-page">
  <header class="site-header research-header">
    <div class="eyebrow">EVIDENCE REVIEW COMPLETED</div>
    <h1>確認済みの<br><span>学習カードへ</span></h1>
    <p class="lead">旧調査ページの確認待ち項目は、出典と適用条件を確認・修正し、学習カードへ移しました。現在、根拠確認中のカードはありません。</p>
    <p><a href="{escape(home_url)}">鉄骨構造の問題を解く →</a></p>
  </header>
  <main id="research-items" data-research-catalog-root>
    <h2>以前の固定リンクから探す</h2>
    {sections}
  </main>
  <script src="{escape(script_url)}" defer></script>
</body>
</html>'''
    summary = (
        "根拠確認中の鉄骨構造項目について、暫定内容と分かりやすい解説を探す"
        "Google検索ボタンを掲載する調査ページ。"
    )
    return f"""<!doctype html>
<html lang="ja" class="research-document">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>根拠を調べる — 鉄骨構造 原理台帳</title>
  <meta name="description" content="{escape(summary)}">
  <meta name="robots" content="noindex,follow">
  <link rel="canonical" href="{escape(canonical_url)}">
  <link rel="stylesheet" href="{escape(stylesheet_url)}">
</head>
<body class="research-page">
  <a class="skip-link" href="#research-items">調査項目へ移動</a>
  <header class="site-header research-header">
    <div class="eyebrow">FIRST-CLASS ARCHITECT / EVIDENCE REVIEW</div>
    <p class="research-back-link"><a href="{escape(home_url)}">← 確認済みの原理台帳へ</a></p>
    <h1>根拠を<br><span>調べる</span></h1>
    <p class="lead">確認前の内容と、<strong>分かりやすい解説</strong>を探すボタンを公開しています。</p>
    <div class="hero-stats" aria-label="調査ページの項目数">
      <div><strong>{visible_count}</strong><span>暫定問題</span></div>
      <div><strong>{answerable_count}</strong><span>暫定正解あり</span></div>
      <div><strong>{pending_count}</strong><span>判定保留</span></div>
    </div>
  </header>

  <main>
    <section class="research-warning" aria-labelledby="research-warning-title">
      <p>PROVISIONAL CONTENT</p>
      <h2 id="research-warning-title">ここは確認済み学習カードではありません</h2>
      <p>掲載内容は根拠確認前の暫定情報です。誤り、条件不足、複数の論点の混同を含む可能性があります。試験知識として確定せず、リンク先の一次資料や信頼できる解説で該当箇所を確認してください。</p>
      <p class="search-disclosure">「Googleで解説を探す」を開くと、項目ごとの解説向け検索語がGoogleへ送信されます。Googleの検索結果は台帳の根拠ではありません。</p>
      <p>検索語はCodexによる調査結果を反映した監査スナップショットです。検索や内容更新を自動実行する仕組みではありません。</p>
    </section>

    <section class="research-controls" aria-labelledby="research-filter-title">
      <div>
        <p class="control-kicker">CANDIDATE COVERAGE</p>
        <h2 id="research-filter-title">候補層で絞り込む</h2>
        <p>候補層は調査中の学習順案です。確認済み台帳の正式な導入層ではありません。</p>
      </div>
      <label for="research-coverage-filter">表示する候補層
        <select id="research-coverage-filter">
          <option value="all">すべて（{visible_count}件）</option>
          <option value="core-only">骨格のみ（{tier_counts[1]}件）</option>
          <option value="standard-only">標準のみ（{tier_counts[2]}件）</option>
          <option value="advanced-only">発展のみ（{tier_counts[3]}件）</option>
          <option value="core+standard">骨格＋標準（{tier_counts[1] + tier_counts[2]}件）</option>
        </select>
      </label>
      <p class="research-result-summary" aria-live="polite">
        <strong id="research-visible-count">{visible_count}</strong><span> / {visible_count}件を表示</span>
      </p>
    </section>

    <nav class="section-nav research-nav" aria-label="調査分野から探す">{nav}</nav>
    <div id="research-items" class="research-catalog" data-research-catalog-root>{sections}</div>
  </main>

  <footer class="site-footer">
    <p>確認済みへの昇格には、正式資料の出典名・該当箇所・対応範囲の記録が必要です。</p>
    <p>閲覧専用 / Cookie・外部解析なし / 検索語版：v{queries.version}</p>
  </footer>
  <script src="{escape(script_url)}" defer></script>
</body>
</html>
"""


def _page(
    base_url: str,
    catalog: Catalog,
    research_queries: ResearchQueryRegistry,
    exam_audit: ExamCoverageAudit | None = None,
) -> str:
    projection = load_public_progress()
    validate_public_progress(catalog, projection)

    published = display_principles(catalog, published_only=True)
    if not published:
        raise ValueError("no source-checked principles are available for publication")
    type_counts = Counter(item.type for item in published)
    progress_counts = Counter(
        projection.items.get(item.id, "unstarted") for item in published
    )
    research_count = sum(
        item.id in research_queries.items
        and research_queries.items[item.id].has_research_route
        and item.editorial_status != "source_checked"
        for item in catalog.principles
    )
    group_count = len(catalog.taxonomy.groups)
    subtopic_count = sum(len(group.subtopics) for group in catalog.taxonomy.groups)
    canonical_url = urljoin(base_url, "./")
    og_url = urljoin(base_url, "assets/og.png")
    stylesheet_url = _stylesheet_url(base_url)
    script_url = _versioned_asset_url(base_url, "catalog.js")
    research_url = urljoin(base_url, "research/")
    history_script_url = urljoin(base_url, "assets/answer-history.js")
    session_script_url = urljoin(base_url, "assets/study-session.js")
    study_script_url = urljoin(base_url, "assets/study-ui.js")
    practice_script_url = urljoin(base_url, "assets/practice-ui.js")
    practice_variants = load_practice(catalog)
    current_edition = catalog.question_editions.editions[
        catalog.question_editions.current
    ]
    (
        legacy_anchor_aliases,
        legacy_search_aliases,
        identity_route_notices,
    ) = _identity_routes(catalog)
    legacy_section_routes = _legacy_section_routes(catalog, published)
    summary = (
        f"PDF P{catalog.manifest.first_page}-P{catalog.manifest.last_page}の鉄骨構造を、"
        "自作2択問題・正解・内容別の三点で整理した原理台帳。"
    )
    stats = json.dumps(
        {
            "published": len(published),
            "planned": len(catalog.principles),
            "groups": group_count,
            "subtopics": subtopic_count,
            "types": dict(type_counts),
            "progress": dict(progress_counts),
            "coverage_scheme": catalog.coverage.current,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>鉄骨構造 原理台帳</title>
  <meta name="description" content="{escape(summary)}">
  <link rel="canonical" href="{escape(canonical_url)}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="鉄骨構造 原理台帳">
  <meta property="og:description" content="{escape(summary)}">
  <meta property="og:url" content="{escape(canonical_url)}">
  <meta property="og:image" content="{escape(og_url)}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="stylesheet" href="{escape(stylesheet_url)}">
  <script defer src="{escape(history_script_url)}"></script>
  <script defer src="{escape(session_script_url)}"></script>
  <script defer src="{escape(script_url)}"></script>
  <script defer src="{escape(study_script_url)}"></script>
  <script defer src="{escape(practice_script_url)}"></script>
</head>
<body class="study-page">
  <a class="skip-link" href="#catalog">原理一覧へ移動</a>
  <header class="site-header">
    <h1>鉄骨構造 <span>原理台帳</span></h1>
    <details class="catalog-about">
      <summary>台帳について</summary>
    <p class="lead">2択から結論を選び、<strong>理由・条件</strong>までつなげて理解する。</p>
    <div class="scope-note">対象：教材の鉄骨構造（PDF P{catalog.manifest.first_page}-P{catalog.manifest.last_page}）＋鋼材・合成構造・耐震設計の関連論点</div>
    <div class="hero-stats" aria-label="台帳の収録範囲">
      <div><strong>{len(published)}</strong><span>公開項目</span></div>
      <div><strong>{group_count}</strong><span>大項目</span></div>
      <div><strong>{subtopic_count}</strong><span>小項目</span></div>
    </div>
    {f'''<details class="exam-scope">
      <summary>教材・本試験との対応範囲</summary>
      <p><a href="{escape(exam_audit.index_url)}" target="_blank" rel="noopener noreferrer">2017–2026年の公式問題</a>の構造{exam_audit.questions}問・全選択肢から鉄骨関連{exam_audit.steel_questions}問を選別。学習目標{exam_audit.objectives}件のうち、成立条件と設問の対応を{exam_audit.verified}件確認しています。</p>
      <p>一般力学の基礎問題は別枠です。過去10年の対応は将来の全出題や合格を保証しません。図は独自の学習用模式図で、試験原図の転載ではありません。</p>
    </details>''' if exam_audit else ''}
    </details>
  </header>

  <main>
    <section id="study-dashboard" class="study-dashboard" aria-labelledby="study-dashboard-title" hidden>
      <div class="study-dashboard-heading">
        <h2 id="study-dashboard-title" class="visually-hidden">今日の学習</h2>
        <label class="select-field">
          <span>学習範囲</span>
          <select id="study-tier">
            <option value="1">骨格</option>
            <option value="2">骨格＋標準</option>
            <option value="3">全層</option>
          </select>
        </label>
      </div>
      <div class="study-actions">
        <button type="button" class="study-primary" id="study-start">今日の10問</button>
        <button type="button" id="study-resume" hidden>続きから</button>
        <button type="button" id="study-review">今日の復習</button>
        <button type="button" id="study-browse" aria-label="一覧から探す">一覧・検索</button>
      </div>
      <details class="study-progress-summary">
        <summary>成績・小項目の現在地</summary>
        <p class="study-guide">復習は最大5問、残りは未回答から。足りない日は10問未満で終わります。</p>
        <div id="study-metrics" class="study-metrics" aria-label="この端末の回答状況"></div>
        <details id="study-map" class="study-map">
          <summary>小項目ごとの現在地を見る</summary>
          <p>回答の記録です。正解数だけで習得や合格を判定するものではありません。</p>
          <div id="study-map-content"></div>
        </details>
      </details>
    </section>
    {f'''<section class="research-entry" aria-labelledby="research-entry-title">
      <div>
        <p class="section-kicker">EVIDENCE REVIEW</p>
        <h2 id="research-entry-title">根拠確認中の項目を調べる</h2>
        <p>根拠確認中の{research_count}件について、暫定内容と「Googleで解説を探す」ボタンを別ページに分けました。</p>
      </div>
      <a href="{escape(research_url)}">根拠確認中の項目を見る <span aria-hidden="true">→</span></a>
    </section>''' if research_count else ''}

    <section class="study-history-controls" aria-labelledby="study-history-title">
      <details>
      <summary id="study-history-title">使い方・履歴の管理</summary>
      <p>履歴はこの端末のブラウザ内だけに保存します。端末間の自動同期はありません。ブラウザのデータ削除に備えてバックアップしてください。</p>
      <p>各問題の☆でお気に入りを登録・解除できます。「一覧・検索」の「お気に入りのみ」で絞り込めます。お気に入りもこのブラウザ内だけに保存され、履歴のバックアップには含まれません。</p>
      <p>A/Bを選ぶと初回回答を採点・保存します。解説を見るだけでは回答になりません。答えを見た日の解き直しは練習として記録し、独力の成績には含めません。</p>
      <p>カード下部の目アイコンで正解・解説、iアイコンで補助情報、回転矢印でもう一度解けます。各アイコンには操作名のツールチップがあります。</p>
      <p>誤答は要復習、独力で2回連続誤答すると重点復習。日を分けた初回回答で2回連続正解すると復習対象から外れます。合格や習得を保証する判定ではありません。</p>
      <p>今日の復習には、まだ答えを見ていない日の問題を選びます。一覧の「要復習」からは同じ日の練習もできます。</p>
      <p class="search-disclosure">「Googleで解説を探す」を開くと、項目ごとの解説向け検索語がGoogleへ送信されます。Googleの検索結果は台帳の根拠ではありません。</p>
      <div class="history-backup-actions">
        <button type="button" id="history-export">履歴をバックアップ</button>
        <label>履歴を復元・統合<input id="history-import" type="file" accept="application/json,.json"></label>
      </div>
      </details>
      <noscript><p>回答の採点・保存・絞込みにはJavaScriptが必要です。正解と解説は各カードで開けます。</p></noscript>
    </section>

    <details id="catalog-browser" class="catalog-browser">
      <summary>一覧・検索</summary>
    <section id="catalog-controls" class="controls" aria-labelledby="filter-title" tabindex="-1">
      <div>
        <h2 id="filter-title" class="visually-hidden">一覧から探す</h2>
      </div>
      <label class="search-field">
        <span>キーワード検索</span>
        <input type="search" id="catalog-search" placeholder="例：座屈、アンカーボルト、溶接" autocomplete="off">
      </label>
      <label class="select-field">
        <span>この端末の回答・復習</span>
        <select id="review-filter">
          <option value="all">すべて</option>
          <option value="unanswered">未回答</option>
          <option value="review">要復習（重点を含む）</option>
          <option value="priority">重点復習（連続誤答）</option>
          <option value="history">回答履歴あり</option>
        </select>
      </label>
      <label class="select-field">
        <span>導入層</span>
        <select id="coverage-filter">
          <option value="all">全て</option>
          <option value="core-only">骨格のみ</option>
          <option value="standard-only">標準のみ</option>
          <option value="advanced-only">発展のみ</option>
          <option value="core+standard">骨格＋標準</option>
        </select>
      </label>
      <details class="advanced-filters">
        <summary>詳細条件：種類・学習計画・出典</summary>
        <div class="advanced-filter-fields">
          <fieldset class="filter-group" data-filter-group="type">
            <legend>種類</legend>
            <button type="button" class="filter-chip is-active" data-filter-type="all" aria-pressed="true">すべて</button>
            <button type="button" class="filter-chip" data-filter-type="principle" aria-pressed="false">原理</button>
            <button type="button" class="filter-chip" data-filter-type="rule" aria-pressed="false">規定</button>
            <button type="button" class="filter-chip" data-filter-type="identification" aria-pressed="false">識別</button>
          </fieldset>
          <label class="select-field">
            <span>学習計画の状態（回答履歴とは別）</span>
            <select id="progress-filter">
              <option value="all">すべて</option>
              <option value="unstarted">未学習</option>
              <option value="learning">学習中</option>
              <option value="reviewing">復習中</option>
              <option value="retained_14d">14日保持</option>
            </select>
          </label>
          <label class="select-field">
            <span>出典種別</span>
            <select id="source-kind-filter">
              <option value="all">すべて</option>
              {_source_kind_options(catalog, published)}
            </select>
          </label>
        </div>
      </details>
      <label class="favorite-filter-field"><input type="checkbox" id="favorite-filter">お気に入りのみ</label>
      <p class="result-summary" aria-live="polite"><strong id="visible-count">{len(published)}</strong>件を表示</p>
      <button class="answer-toggle-button" id="toggle-visible-answers" type="button" data-toggle-visible-answers aria-controls="catalog" aria-pressed="false">表示中の答えをすべて開く</button>
      <button class="reset-button" id="reset-filters" type="button">条件をリセット</button>
    </section>

    <nav class="section-nav" aria-label="分野から探す">{_taxonomy_nav(catalog, published)}</nav>
    </details>

    <div class="study-notices">
      <p id="study-status" role="status" aria-live="polite"></p>
      <p id="history-status" role="status" aria-live="polite">履歴はこのブラウザに保存します。</p>
      <p id="favorite-status" role="status" aria-live="polite"></p>
    </div>

    {legacy_section_routes}
    {identity_route_notices}

    <section id="study-session" class="study-session" aria-labelledby="study-session-title" tabindex="-1" hidden>
      <h2 id="study-session-title" class="visually-hidden">今日の10問</h2>
      <div class="study-session-toolbar">
        <p id="study-session-progress" role="status" aria-live="polite"></p>
        <button type="button" id="study-toggle-answers" data-toggle-visible-answers aria-label="表示中の答えをすべて開く" aria-controls="catalog" aria-pressed="false">答えを開く</button>
        <details id="study-session-menu" class="study-session-menu">
          <summary>その他</summary>
          <div class="study-session-actions">
            <button type="button" id="study-finish">今回の学習を終える</button>
            <button type="button" id="study-pause">一覧へ戻る</button>
          </div>
        </details>
      </div>
    </section>
    <p id="study-session-result" class="study-session-result" role="status" aria-live="polite" hidden></p>
    <button type="button" id="study-return" class="study-return" hidden>元の問題へ戻る</button>
    <div id="catalog" class="catalog" data-catalog-root
      data-coverage-scheme="{escape(catalog.coverage.current)}">
      <div id="study-card-list" class="study-card-list" hidden></div>
      {_taxonomy_sections(
          catalog,
          published,
          projection.items,
          current_edition,
          legacy_anchor_aliases,
          legacy_search_aliases,
          research_queries,
          practice_variants,
      )}
      <p class="empty-state" id="empty-state" hidden>条件に一致する原理がありません。</p>
    </div>
  </main>

  <footer class="site-footer">
    <p>2択問題は台帳の内容から作成した自作です。原典の問題文・図版・PDFは掲載していません。</p>
    <p>回答履歴は端末内のみ / Cookie・外部解析なし / 導入層版：{escape(catalog.coverage.current)}</p>
  </footer>
  <script type="application/json" id="catalog-stats">{stats}</script>
</body>
</html>
"""


def _prepare_output(output: Path) -> None:
    if not output.exists():
        return
    marker = output / _OUTPUT_MARKER
    if not marker.is_file() or marker.read_text(encoding="utf-8") != _OUTPUT_MARKER_CONTENT:
        raise ValueError(f"refusing to replace unmarked output directory: {output}")
    shutil.rmtree(output)


def build_site(output: Path, base_url: str) -> tuple[int, int]:
    if not _BASE_URL.fullmatch(base_url):
        raise ValueError("base URL must be an HTTPS directory URL ending in /")
    catalog = load_catalog()
    exam_audit = load_exam_coverage(catalog)
    research_queries = load_research_queries(catalog)
    research_questions = load_research_questions(catalog)
    research_coverage = load_research_coverage(catalog, research_questions)
    published_count = sum(
        item.editorial_status == "source_checked" for item in catalog.principles
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="principle-site-", dir=output.parent) as raw_temp:
        temp = Path(raw_temp)
        assets = temp / "assets"
        research = temp / "research"
        assets.mkdir(parents=True)
        research.mkdir(parents=True)
        root_page = _page(base_url, catalog, research_queries, exam_audit)
        (temp / "index.html").write_text(root_page, encoding="utf-8")
        (temp / "404.html").write_text(root_page, encoding="utf-8")
        (research / "index.html").write_text(
            _research_page(
                base_url,
                catalog,
                research_queries,
                research_questions,
                research_coverage,
            ),
            encoding="utf-8",
        )
        (temp / ".nojekyll").write_text("", encoding="utf-8")
        (temp / _OUTPUT_MARKER).write_text(_OUTPUT_MARKER_CONTENT, encoding="utf-8")
        (assets / "styles.css").write_text(_asset_text("styles.css"), encoding="utf-8")
        (assets / "catalog.js").write_text(_asset_text("catalog.js"), encoding="utf-8")
        (assets / "answer-history.js").write_text(_asset_text("answer-history.js"), encoding="utf-8")
        for asset in ("study-session.js", "study-ui.js", "practice-ui.js"):
            (assets / asset).write_text(_asset_text(asset), encoding="utf-8")
        (assets / "research.js").write_text(
            _asset_text("research.js"),
            encoding="utf-8",
        )
        og_source = Path(__file__).with_name("static") / "og.png"
        if og_source.exists():
            shutil.copy2(og_source, assets / "og.png")
        else:
            raise ValueError("social preview asset is missing")
        _prepare_output(output)
        shutil.move(str(temp), str(output))
    return published_count, len(catalog.principles)
