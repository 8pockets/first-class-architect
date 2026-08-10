"""Build a public, read-only, privacy-bounded static catalog."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import urljoin

from principle_catalog.catalog import (
    load_catalog,
    load_public_progress,
    validate_public_progress,
)
from principle_catalog.models import Principle, PublicProgress


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


def _asset_text(name: str) -> str:
    path = Path(__file__).with_name("static") / name
    return path.read_text(encoding="utf-8")


def _source_label(item: Principle) -> str:
    pages = "・".join(f"P{page}" for page in item.source.pages)
    if not item.source.question_codes:
        return pages
    codes = "・".join(item.source.question_codes)
    return f"{pages} / 問題コード {codes}"


def _condition_list(item: Principle) -> str:
    return "".join(f"<li>{escape(condition)}</li>" for condition in item.conditions)


def _card(item: Principle, progress: PublicProgress) -> str:
    if item.question is None:
        raise ValueError(f"published principle has no confirmation question: {item.id}")
    search_text = " ".join(
        [
            item.principle,
            item.question,
            item.conclusion,
            item.reason,
            *item.conditions,
            item.section_title,
            *item.source.question_codes,
        ]
    )
    return f"""
<article class="principle-card" id="{escape(item.id)}"
  data-type="{escape(item.type)}"
  data-section="{escape(item.section_id)}"
  data-progress="{escape(progress)}"
  data-search="{escape(search_text.lower())}">
  <header class="card-header">
    <div class="badge-row">
      <span class="type-badge type-{escape(item.type)}">{_TYPE_LABELS[item.type]}</span>
      <span class="progress-badge progress-{escape(progress)}">{_PROGRESS_LABELS[progress]}</span>
    </div>
    <p class="card-id">{escape(item.id)}</p>
    <h3>{escape(item.principle)}</h3>
  </header>
  <div class="practice-question">
    <p class="practice-question-label">確認問題（自作）</p>
    <p class="practice-question-text">{escape(item.question)}</p>
  </div>
  <dl class="three-point">
    <div>
      <dt>結論</dt>
      <dd>{escape(item.conclusion)}</dd>
    </div>
    <div>
      <dt>理由</dt>
      <dd>{escape(item.reason)}</dd>
    </div>
    <div>
      <dt>結論を左右する条件</dt>
      <dd><ul>{_condition_list(item)}</ul></dd>
    </div>
  </dl>
  <footer class="card-source">
    <span>{escape(_source_label(item))}</span>
    <a href="#{escape(item.id)}" aria-label="{escape(item.principle)}への固定リンク">#</a>
  </footer>
</article>""".strip()


def _section_nav(items: tuple[Principle, ...]) -> str:
    seen: set[str] = set()
    links: list[str] = []
    for item in items:
        if item.section_id in seen:
            continue
        seen.add(item.section_id)
        count = sum(1 for candidate in items if candidate.section_id == item.section_id)
        links.append(
            f'<a href="#section-{escape(item.section_id)}">'
            f"{escape(item.section_title)}<span>{count}</span></a>"
        )
    return "".join(links)


def _sections(items: tuple[Principle, ...], progress: dict[str, PublicProgress]) -> str:
    grouped: dict[str, list[Principle]] = {}
    for item in items:
        grouped.setdefault(item.section_id, []).append(item)
    rendered: list[str] = []
    for section_items in grouped.values():
        first = section_items[0]
        cards = "\n".join(
            _card(item, progress.get(item.id, "unstarted")) for item in section_items
        )
        rendered.append(
            f"""
<section class="catalog-section" id="section-{escape(first.section_id)}" data-catalog-section>
  <div class="section-heading">
    <p>{escape(first.section_id)}</p>
    <h2>{escape(first.section_title)}</h2>
    <span>{len(section_items)}件</span>
  </div>
  <div class="card-grid">{cards}</div>
</section>""".strip()
        )
    return "\n".join(rendered)


def _page(base_url: str) -> str:
    catalog = load_catalog()
    projection = load_public_progress()
    validate_public_progress(catalog, projection)

    published = tuple(
        item for item in catalog.principles if item.editorial_status == "source_checked"
    )
    if not published:
        raise ValueError("no source-checked principles are available for publication")
    type_counts = Counter(item.type for item in published)
    progress_counts = Counter(
        projection.items.get(item.id, "unstarted") for item in published
    )
    canonical_url = urljoin(base_url, "./")
    og_url = urljoin(base_url, "assets/og.png")
    stylesheet_url = urljoin(base_url, "assets/styles.css")
    script_url = urljoin(base_url, "assets/catalog.js")
    summary = (
        f"PDF P{catalog.manifest.first_page}-P{catalog.manifest.last_page}の鉄骨構造を、"
        "自作問題・結論・理由・条件で整理した原理台帳。"
    )
    stats = json.dumps(
        {
            "published": len(published),
            "planned": len(catalog.principles),
            "types": dict(type_counts),
            "progress": dict(progress_counts),
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
  <script defer src="{escape(script_url)}"></script>
</head>
<body>
  <a class="skip-link" href="#catalog">原理一覧へ移動</a>
  <header class="site-header">
    <div class="eyebrow">FIRST-CLASS ARCHITECT / STEEL STRUCTURE</div>
    <h1>鉄骨構造<br><span>原理台帳</span></h1>
    <p class="lead">自作問題から考え、<strong>結論・理由・条件</strong>のつながりを見渡す。</p>
    <div class="scope-note">対象：2026 構造・文章問題 / PDF P{catalog.manifest.first_page}-P{catalog.manifest.last_page}</div>
    <div class="hero-stats" aria-label="台帳の進捗">
      <div><strong>{len(published)}</strong><span>出典確認済み</span></div>
      <div><strong>{len(catalog.principles)}</strong><span>台帳化済み</span></div>
      <div><strong>{len({item.section_id for item in published})}</strong><span>公開セクション</span></div>
    </div>
  </header>

  <main>
    <section class="controls" aria-labelledby="filter-title">
      <div>
        <p class="section-kicker">FIND A PRINCIPLE</p>
        <h2 id="filter-title">今日確かめたい関係を探す</h2>
      </div>
      <label class="search-field">
        <span>キーワード検索</span>
        <input type="search" id="catalog-search" placeholder="例：座屈、アンカーボルト、溶接" autocomplete="off">
      </label>
      <fieldset class="filter-group" data-filter-group="type">
        <legend>種類</legend>
        <button type="button" class="filter-chip is-active" data-filter-type="all" aria-pressed="true">すべて</button>
        <button type="button" class="filter-chip" data-filter-type="principle" aria-pressed="false">原理</button>
        <button type="button" class="filter-chip" data-filter-type="rule" aria-pressed="false">規定</button>
        <button type="button" class="filter-chip" data-filter-type="identification" aria-pressed="false">識別</button>
      </fieldset>
      <label class="select-field">
        <span>学習状態</span>
        <select id="progress-filter">
          <option value="all">すべて</option>
          <option value="unstarted">未学習</option>
          <option value="learning">学習中</option>
          <option value="reviewing">復習中</option>
          <option value="retained_14d">14日保持</option>
        </select>
      </label>
      <p class="result-summary" aria-live="polite"><strong id="visible-count">{len(published)}</strong>件を表示</p>
      <button class="reset-button" id="reset-filters" type="button">条件をリセット</button>
    </section>

    <nav class="section-nav" aria-label="章・節から探す">{_section_nav(published)}</nav>

    <div id="catalog" class="catalog" data-catalog-root>
      {_sections(published, projection.items)}
      <p class="empty-state" id="empty-state" hidden>条件に一致する原理がありません。</p>
    </div>
  </main>

  <footer class="site-footer">
    <p>確認問題は台帳の内容から作成した自作です。原典の問題文・図版・PDFは掲載していません。</p>
    <p>閲覧専用 / Cookie・外部解析なし</p>
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
    published_count = sum(
        item.editorial_status == "source_checked" for item in catalog.principles
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="principle-site-", dir=output.parent) as raw_temp:
        temp = Path(raw_temp)
        assets = temp / "assets"
        assets.mkdir(parents=True)
        (temp / "index.html").write_text(_page(base_url), encoding="utf-8")
        (temp / "404.html").write_text(_page(base_url), encoding="utf-8")
        (temp / ".nojekyll").write_text("", encoding="utf-8")
        (temp / _OUTPUT_MARKER).write_text(_OUTPUT_MARKER_CONTENT, encoding="utf-8")
        (assets / "styles.css").write_text(_asset_text("styles.css"), encoding="utf-8")
        (assets / "catalog.js").write_text(_asset_text("catalog.js"), encoding="utf-8")
        og_source = Path(__file__).with_name("static") / "og.png"
        if og_source.exists():
            shutil.copy2(og_source, assets / "og.png")
        else:
            raise ValueError("social preview asset is missing")
        _prepare_output(output)
        shutil.move(str(temp), str(output))
    return published_count, len(catalog.principles)
