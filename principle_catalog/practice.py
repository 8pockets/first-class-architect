"""Optional, source-bounded variants, separate from the published card inventory."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import cast

from principle_catalog.catalog import CATALOG_ROOT, CatalogError, _load_yaml
from principle_catalog.models import Catalog, ChoiceLabel


PRACTICE_PATH = CATALOG_ROOT / "practice.yaml"
_FIELDS = {
    "id", "parent_id", "title", "prompt", "choices", "correct", "explanation",
    "source_pages", "source_note", "figure",
}
_SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
# SVG is code-owned. YAML can select a reviewed template, never supply markup.
_FIGURES = {
    "weld-symbol-above": (
        "基準線の上に三角形の基本記号がある溶接指示。左端の矢印は接合部を指す。",
        '<path d="M45 170 L100 110 H305" fill="none" stroke="currentColor" stroke-width="3"/>'
        '<path d="M45 170 L48 151 L62 161 Z" fill="currentColor"/>'
        '<path d="M180 110 V72 L218 110 Z" fill="none" stroke="currentColor" stroke-width="3"/>'
        '<text x="245" y="140">基準線</text>'
        '<text x="25" y="200">矢印</text>',
    ),
    "h-section-axes": (
        "上下の横板と中央の縦板からなる二軸対称H形断面。重心を通る水平軸がx、鉛直軸がy。",
        '<path d="M110 45 H230 V67 H181 V193 H230 V215 H110 V193 H159 V67 H110 Z" '
        'fill="#cbd5e1" stroke="currentColor" stroke-width="2"/>'
        '<path d="M65 130 H280 M170 20 V240" stroke="currentColor" stroke-width="2" stroke-dasharray="6 4"/>'
        '<text x="286" y="136">x</text><text x="180" y="27">y</text>',
    ),
    "h-section-parts": (
        "H形断面の上下の横板をP、中央の縦板をQと表示した模式図。",
        '<path d="M110 45 H230 V67 H181 V193 H230 V215 H110 V193 H159 V67 H110 Z" '
        'fill="#cbd5e1" stroke="currentColor" stroke-width="2"/>'
        '<path d="M230 56 H267 M230 204 H267 M181 130 H267" stroke="currentColor" stroke-width="2"/>'
        '<text x="277" y="63">P</text><text x="277" y="211">P</text>'
        '<text x="277" y="137">Q</text>',
    ),
}


@dataclass(frozen=True)
class PracticeVariant:
    id: str
    parent_id: str
    item_id: str
    title: str
    prompt: str
    choice_a: str
    choice_b: str
    correct: ChoiceLabel
    explanation: str
    source_pages: tuple[int, ...]
    source_note: str
    figure: str | None
    revision: str


def load_practice(
    catalog: Catalog, path: Path = PRACTICE_PATH,
) -> dict[str, list[PracticeVariant]]:
    """Validate optional variants without changing the canonical 311-card set."""

    document = _load_yaml(path)

    def fail(message: str) -> None:
        raise CatalogError(f"{path}: {message}")

    if set(document) != {"version", "variants"} or type(document.get("version")) is not int or document["version"] != 1:
        fail("practice must contain version 1 and variants only")
    rows = document["variants"]
    if not isinstance(rows, list):
        fail("variants must be a list")
    parents = {item.id: item for item in catalog.principles}
    result: dict[str, list[PracticeVariant]] = {}
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        label = f"variants[{index}]"
        if not isinstance(raw, dict) or set(raw) != _FIELDS:
            fail(f"{label} has missing or unexpected fields")
        for field in ("id", "parent_id", "title", "prompt", "correct", "explanation", "source_note"):
            if not isinstance(raw[field], str) or not raw[field].strip():
                fail(f"{label}.{field} must be a non-empty string")
        slug = raw["id"]
        if not _SLUG.fullmatch(slug) or len(slug) > 60 or slug in seen:
            fail(f"{label}.id must be a unique stable slug of at most 60 characters")
        seen.add(slug)
        parent = parents.get(raw["parent_id"])
        if parent is None or parent.editorial_status != "source_checked" or parent.question is None:
            fail(f"{label}.parent_id must name a published source-checked card")
        choices = raw["choices"]
        if not isinstance(choices, dict) or set(choices) != {"A", "B"} or any(
            not isinstance(choice, str) or not choice.strip() for choice in choices.values()
        ):
            fail(f"{label}.choices must contain non-empty A and B")
        if choices["A"].strip() == choices["B"].strip() or raw["correct"] not in {"A", "B"}:
            fail(f"{label} must have distinct choices and one correct label")
        pages = raw["source_pages"]
        if not isinstance(pages, list) or not pages or any(type(page) is not int for page in pages):
            fail(f"{label}.source_pages must contain page integers")
        if len(set(pages)) != len(pages) or not set(pages).issubset(parent.source.pages):
            fail(f"{label}.source_pages must be distinct verified pages of its parent")
        figure = raw["figure"]
        if figure is not None and (not isinstance(figure, str) or figure not in _FIGURES):
            fail(f"{label}.figure must select a reviewed template")
        item_id = f"practice:{parent.code}:{slug}"
        if not re.fullmatch(r"[a-zA-Z0-9._:-]{1,200}", item_id):
            fail(f"{label} generates an invalid history identifier")
        # A changed diagram, answer, or explanation also requires reconfirmation.
        payload = {**raw, "figure_template": _FIGURES.get(figure) if figure else None}
        revision = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        variant = PracticeVariant(
            id=slug, parent_id=parent.id, item_id=item_id,
            title=raw["title"], prompt=raw["prompt"],
            choice_a=choices["A"], choice_b=choices["B"],
            correct=cast(ChoiceLabel, raw["correct"]), explanation=raw["explanation"],
            source_pages=tuple(pages), source_note=raw["source_note"],
            figure=figure, revision=revision,
        )
        result.setdefault(parent.id, []).append(variant)
    return result


def render_practice(variant: PracticeVariant) -> str:
    """Render safe, progressively enhanced markup for optional separate practice."""

    dom_id = f"practice-{variant.id}"
    answer_id = f"{dom_id}-answer"
    result_id = f"{dom_id}-result"
    figure_html = ""
    if variant.figure is not None:
        if variant.figure not in _FIGURES:
            raise CatalogError("practice figure must select a reviewed template")
        description, shape = _FIGURES[variant.figure]
        figure_html = (
            '<figure class="practice-figure">'
            f'<svg viewBox="0 0 340 260" role="img" aria-labelledby="{escape(dom_id)}-figure-title" '
            'style="max-width:100%;height:auto" '
            'width="340" height="260" font-size="18" font-family="sans-serif">'
            f'<title id="{escape(dom_id)}-figure-title">{escape(description)}</title>{shape}</svg>'
            '<figcaption>理解確認のための自作模式図（縮尺・細部は省略）。</figcaption></figure>'
        )
    buttons = "".join(
        f'<button type="button" class="practice-choice" data-practice-choice="{label}" '
        f'aria-controls="{escape(answer_id)}" aria-describedby="{escape(result_id)}">'
        f'<span class="choice-label">{label}</span> {escape(text)}</button>'
        for label, text in (("A", variant.choice_a), ("B", variant.choice_b))
    )
    pages = "・".join(f"P{page}" for page in variant.source_pages)
    return f"""
<details class="practice-panel" data-practice-panel
  data-practice-id="{escape(variant.item_id)}" data-practice-parent-id="{escape(variant.parent_id)}"
  data-practice-revision="{escape(variant.revision)}" data-correct-choice="{escape(variant.correct)}">
  <summary>追加確認（本体の成績とは別）：{escape(variant.title)}</summary>
  <div class="practice-body">
    <p class="practice-note">任意の練習です。回答は追加確認として別に記録し、本体の進捗・成績には含めません。</p>
    <p class="practice-prompt">{escape(variant.prompt)}</p>
    {figure_html}
    <div class="practice-choices" role="group" aria-label="追加確認の選択肢">{buttons}</div>
    <p id="{escape(result_id)}" class="practice-result" data-practice-result role="status" aria-live="polite"></p>
    <details id="{escape(answer_id)}" class="practice-answer" data-practice-answer>
      <summary>追加確認の答え・解説</summary>
      <p><strong>正解：{escape(variant.correct)}</strong></p>
      <p>{escape(variant.explanation)}</p>
      <p class="practice-source">根拠：教材{escape(pages)}。{escape(variant.source_note)}</p>
    </details>
  </div>
</details>"""
