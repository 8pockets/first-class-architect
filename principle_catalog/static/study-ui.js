/* Finite study sessions reuse the catalogue's cards and private answer store. */
(() => {
  "use strict";
  const catalog = globalThis.ArchitectCatalog;
  const engine = globalThis.ArchitectStudySession;
  const history = globalThis.ArchitectAnswerHistory;
  const dashboard = document.getElementById("study-dashboard");
  if (!catalog || !engine || !history || !dashboard) return;
  const $ = (id) => document.getElementById(id);
  const tier = $("study-tier");
  const status = $("study-status");
  const bar = $("study-session");
  const title = $("study-session-title");
  const progress = $("study-session-progress");
  const result = $("study-session-result");
  const resume = $("study-resume");
  const controls = $("catalog-controls");
  const browser = $("catalog-browser");
  const menu = $("study-session-menu");
  const nav = document.querySelector('nav[aria-label="分野から探す"]');
  const returnButton = $("study-return");
  const labels = { 1: "骨格", 2: "骨格＋標準", 3: "骨格＋標準＋発展" };
  const items = catalog.cards.map((card) => ({
    itemId: card.dataset.studyId, revision: card.dataset.questionRevision,
    tier: Number(card.dataset.coverageTier), order: Number(card.dataset.introductionOrder),
    group: card.dataset.group, section: card.dataset.section,
  }));
  const byId = new Map(catalog.cards.map((card) => [card.dataset.studyId, card]));
  let store = null;
  let state = null;
  let active = false;
  let blocked = false;
  let unsaved = false;
  const returnStack = [];
  const auxiliaryIds = [];
  const message = (text, error = false) => {
    status.textContent = text;
    status.dataset.error = String(error);
  };
  const protect = (action) => (...args) => {
    try { action(...args); }
    catch (error) { message(error.message, true); }
  };
  const localDay = () => history.localDay(new Date());
  const persist = () => {
    try { store.write(state); unsaved = false; }
    catch (error) {
      unsaved = true;
      message(`進行位置を保存できません。この画面内では続けられます。${error.message}`, true);
    }
    resume.textContent = unsaved ? "続きから（この画面内）" : "続きから";
  };
  const canResume = () => Boolean(state?.items.length && state.index < state.items.length);
  const syncResume = () => { resume.hidden = !canResume() || active; };
  const clearSetLabels = () => {
    for (const card of catalog.cards) {
      card.querySelector(".study-set-position")?.remove();
      card.classList.toggle("study-set-supplement", false);
    }
  };
  const setMode = (enabled) => {
    active = enabled;
    if (!enabled) clearSetLabels();
    document.body.classList.toggle("is-studying", enabled);
    bar.hidden = !enabled;
    if (!enabled) result.hidden = true;
    if (menu) menu.open = false;
    if (browser) browser.hidden = enabled;
    controls.hidden = enabled;
    if (nav) nav.hidden = enabled;
    catalog.root.classList.toggle("study-session-active", enabled);
    syncResume();
  };
  const focusCard = (card) => {
    if (!card) return;
    card.setAttribute("tabindex", "-1");
    card.focus({ preventScroll: true });
    card.scrollIntoView({ block: "start", behavior: "instant" });
  };
  const nextUnansweredIndex = (value) => {
    const index = value.items.findIndex((item) => !value.done.includes(item.itemId));
    return index < 0 ? value.items.length : index;
  };
  // Old one-card sessions may point past a skipped question. Resume the same
  // saved set at its first unanswered card, while keeping deliberate endings.
  const normalizePosition = (value) => engine.setIndex(value,
    value.index >= value.items.length ? value.items.length : nextUnansweredIndex(value));
  const updateSessionText = () => {
    if (!state) return;
    const finished = state.index >= state.items.length;
    title.textContent = finished ? "今回のセットを終了しました" :
      `${labels[state.tier]} · ${state.mode === "review" ? "今日の復習" : "今日の学習セット"}`;
    progress.textContent = finished ? `終了 ${state.done.length}/${state.items.length}` : `${state.done.length} / ${state.items.length}問`;
    progress.setAttribute("aria-label", `${finished ? "今回の学習を終了。" : ""}回答 ${state.done.length} / ${state.items.length}問 · 残り ${state.items.length - state.done.length}問`);
    $("study-finish").disabled = finished;
    result.hidden = !active || !finished;
    if (finished) {
      const events = catalog.readEvents();
      const pending = state.items.filter((item) => history.summarize(events, item.itemId, item.revision).review).length;
      result.textContent = `今回の回答 ${state.done.length} / ${state.items.length}問。要復習 ${pending}問。` +
        (state.done.length < state.items.length ? "未回答の問題は、次のセットでも選ばれます。" : "") +
        "答えを見た日の解き直しは練習です。後日、独力で確かめましょう。";
    }
    syncResume();
  };
  const labelSetCards = () => {
    const selected = new Map(state.items.map((item, index) => [item.itemId, { item, index }]));
    for (const itemId of [...selected.keys(), ...auxiliaryIds]) {
      const card = byId.get(itemId);
      if (!card || card.querySelector(".study-set-position")) continue;
      const label = document.createElement("p");
      label.className = "study-set-position";
      const entry = selected.get(itemId);
      card.classList.toggle("study-set-supplement", !entry);
      label.textContent = entry
        ? `第${entry.index + 1}問 · ${entry.item.kind === "review" ? "復習" : "新規"} · ${card.dataset.groupTitle}`
        : `前提を確認（セットの集計対象外） · ${card.dataset.groupTitle}`;
      card.prepend(label);
    }
  };
  const showSet = () => {
    setMode(true);
    returnStack.length = 0;
    auxiliaryIds.length = 0;
    if (returnButton) returnButton.hidden = true;
    clearSetLabels();
    catalog.showCards(state.items.map((item) => item.itemId), { ordered: true });
    labelSetCards();
    // This is a deliberate end state, not a failed catalogue search.
    $("empty-state").hidden = true;
    updateSessionText();
    const current = state.items[state.index] || state.items[0];
    if (current) focusCard(byId.get(current.itemId));
  };
  const refreshDashboard = () => {
    const events = catalog.readEvents();
    const totals = engine.summarizeProgress({ items, events, day: localDay() });
    const metrics = $("study-metrics");
    const cells = [
      [totals.unanswered, "未回答"], [totals.review, "要復習（重点を含む）"],
      [totals.priority, "重点復習"], [totals.todayAnswered, "本日回答した論点"],
    ].map(([count, label]) => {
      const cell = document.createElement("div");
      const number = document.createElement("strong");
      const caption = document.createElement("span");
      number.textContent = String(count); caption.textContent = label;
      cell.append(number, caption);
      return cell;
    });
    metrics.replaceChildren(...cells);
    const container = $("study-map-content");
    const groups = new Map();
    for (const [sectionId, counts] of Object.entries(totals.bySection)) {
      const card = catalog.cards.find((candidate) => candidate.dataset.section === sectionId);
      if (!card) continue;
      if (!groups.has(counts.group)) {
        const section = document.createElement("section");
        const heading = document.createElement("h3");
        const list = document.createElement("ul");
        heading.textContent = card.dataset.groupTitle;
        section.append(heading, list);
        groups.set(counts.group, { section, list });
      }
      const row = document.createElement("li");
      const link = document.createElement("a");
      link.href = `#subtopic-${sectionId}`;
      link.textContent = `${card.dataset.sectionTitle}：回答 ${counts.total - counts.unanswered}/${counts.total} · 要復習 ${counts.review}`;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        leaveSession();
        catalog.showCards(items.filter((item) => item.section === sectionId).map((item) => item.itemId));
        const target = document.getElementById(`subtopic-${sectionId}`);
        target?.scrollIntoView({ block: "start" });
        message("小項目の全問題を表示しています。検索条件を操作すると通常の絞り込みへ戻ります。");
      });
      row.append(link); groups.get(counts.group).list.append(row);
    }
    container.replaceChildren(...[...groups.values()].map(({ section }) => section));
    // A next layer is suggested, never automatically selected or locked.
    let suggestion = $("study-next-tier");
    if (!suggestion) {
      suggestion = document.createElement("button");
      suggestion.id = "study-next-tier"; suggestion.type = "button";
      suggestion.addEventListener("click", protect(() => {
        tier.value = String(Number(tier.value) + 1);
        start("mixed");
      }));
      dashboard.append(suggestion);
    }
    const currentTier = Number(tier.value);
    const layerComplete = items.filter((item) => item.tier <= currentTier)
      .every((item) => !history.summarize(events, item.itemId, item.revision).unanswered);
    suggestion.hidden = currentTier >= 3 || !layerComplete;
    suggestion.textContent = currentTier === 1 ? "骨格を一周しました。標準へ進む" : "標準まで一周しました。発展へ進む";
  };
  function leaveSession() {
    setMode(false);
    returnStack.length = 0;
    auxiliaryIds.length = 0;
    if (returnButton) returnButton.hidden = true;
    catalog.applyFilters();
  }
  function start(mode) {
    if (blocked) throw new Error("保存済みの学習セットを読み取れません。データは変更していません。");
    const chosen = engine.selectItems({ items, events: catalog.readEvents(), tier: Number(tier.value), mode, day: localDay() });
    if (!chosen.length) {
      message(mode === "review" ? "今日、独力で確認できる復習はありません。同日の練習は一覧からできます。" :
        "この範囲で今日出せる未回答・復習問題はありません。次の層、または一覧からの練習を選べます。");
      refreshDashboard();
      return;
    }
    state = engine.createSession({ items: chosen, tier: Number(tier.value), mode });
    persist();
    if (!unsaved) message(`${chosen.length}問を1ページにまとめました。上下にスクロールして、自分のペースで回答できます。途中で離れても、同じセットの未回答から再開できます。`);
    showSet();
  }
  dashboard.hidden = false;
  try {
    store = engine.createStore({ storage: window.localStorage });
    const stored = store.read();
    if (stored) {
      const reconciled = engine.reconcileSession(stored, items);
      state = normalizePosition(reconciled);
      tier.value = String(state.tier);
      if (JSON.stringify(state) !== JSON.stringify(stored)) {
        persist();
        if (!unsaved) message(JSON.stringify(reconciled) !== JSON.stringify(stored)
          ? "問題の更新を反映しました。過去の回答は保持し、変更された問題を再確認します。"
          : "保存済みの問題と回答を保持し、未回答の先頭から再開できるようにしました。");
      }
    }
    refreshDashboard(); syncResume();
  } catch (error) {
    blocked = true;
    $("study-start").disabled = true; $("study-review").disabled = true; resume.disabled = true;
    message(`${error.message} 保存済みデータは削除していません。一覧での閲覧は続けられます。`, true);
  }
  $("study-start").addEventListener("click", protect(() => start("mixed")));
  $("study-review").addEventListener("click", protect(() => start("review")));
  resume.addEventListener("click", protect(() => {
    if (!state) return;
    state = normalizePosition(engine.reconcileSession(state, items));
    tier.value = String(state.tier);
    showSet();
  }));
  $("study-finish").addEventListener("click", protect(() => {
    if (!state) return;
    state = engine.setIndex(state, state.items.length); persist(); updateSessionText();
    if (menu) { menu.open = false; menu.querySelector("summary")?.focus({ preventScroll: true }); }
  }));
  $("study-pause").addEventListener("click", protect(() => {
    leaveSession(); dashboard.scrollIntoView({ block: "start" });
    (resume.hidden ? $("study-start") : resume).focus({ preventScroll: true });
  }));
  $("study-browse").addEventListener("click", protect(() => {
    leaveSession(); if (browser) browser.open = true;
    controls.scrollIntoView({ block: "start" }); $("catalog-search").focus({ preventScroll: true });
  }));
  menu?.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.preventDefault(); menu.open = false;
    menu.querySelector("summary")?.focus({ preventScroll: true });
  });
  document.addEventListener("click", (event) => {
    if (menu?.open && !event.target.closest?.("#study-session-menu")) menu.open = false;
  });
  tier.addEventListener("change", protect(refreshDashboard));
  document.addEventListener("architect:history", protect(() => { refreshDashboard(); if (active) updateSessionText(); }));
  document.addEventListener("architect:answer", protect((event) => {
    if (!state) return;
    const { itemId, revision } = event.detail;
    if (!state.items.some((item) => item.itemId === itemId && item.revision === revision)) return;
    state = normalizePosition(engine.markDone(state, itemId)); persist(); updateSessionText();
  }));
  document.addEventListener("architect:filters", () => {
    setMode(false);
    auxiliaryIds.length = 0;
    returnStack.length = 0;
    if (returnButton) returnButton.hidden = true;
  });
  for (const link of document.querySelectorAll("[data-prerequisite-link]")) {
    link.addEventListener("click", (event) => {
      const target = byId.get(link.dataset.prerequisiteLink);
      if (!target) return;
      event.preventDefault();
      returnStack.push({ active, ids: catalog.cards.filter((card) => !card.hidden).map((card) => card.dataset.studyId),
        from: link.closest(".principle-card")?.dataset.studyId });
      if (active) {
        if (target.hidden) {
          auxiliaryIds.push(target.dataset.studyId);
          catalog.showCards([...state.items.map((item) => item.itemId), ...auxiliaryIds],
            { ordered: true, preserveAnswers: true });
          labelSetCards();
        }
      } else {
        catalog.showCards([target.dataset.studyId]);
      }
      if (returnButton) returnButton.hidden = false;
      focusCard(target);
    });
  }
  returnButton?.addEventListener("click", () => {
    const previous = returnStack.pop();
    if (!previous) return;
    if (!previous.active) catalog.showCards(previous.ids);
    returnButton.hidden = returnStack.length === 0;
    focusCard(byId.get(previous.from));
  });
  window.addEventListener("hashchange", () => {
    let id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); } catch { return; }
    const target = catalog.cards.find((card) => card.id === id);
    if (!target || !target.hidden) return;
    leaveSession();
    catalog.showCards([target.dataset.studyId]);
    focusCard(target);
    message("固定リンクの問題を表示しています。一覧へ戻ると元の絞り込みに戻ります。");
  });
})();
