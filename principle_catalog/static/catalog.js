(() => {
  "use strict";

  const root = document.querySelector("[data-catalog-root]");
  const search = document.querySelector("#catalog-search");
  const progress = document.querySelector("#progress-filter");
  const sourceKind = document.querySelector("#source-kind-filter");
  const coverage = document.querySelector("#coverage-filter");
  const reviewFilter = document.querySelector("#review-filter");
  const historyStatus = document.querySelector("#history-status");
  const historyExport = document.querySelector("#history-export");
  const historyImport = document.querySelector("#history-import");
  const toggleVisibleAnswers = document.querySelector("#toggle-visible-answers");
  const answerToggleButtons = [toggleVisibleAnswers, document.querySelector("#study-toggle-answers")].filter(Boolean);
  const typeButtons = [...document.querySelectorAll("[data-filter-type]")];
  const reset = document.querySelector("#reset-filters");
  const visibleCount = document.querySelector("#visible-count");
  const empty = document.querySelector("#empty-state");

  if (
    !root ||
    !search ||
    !progress ||
    !sourceKind ||
    !coverage ||
    !reset ||
    !visibleCount ||
    !empty
  ) {
    return;
  }

  const cards = [...root.querySelectorAll(".principle-card")];
  const sections = [...root.querySelectorAll("[data-catalog-section]")];
  const groups = [...root.querySelectorAll("[data-catalog-group]")];
  const disclosures = [...root.querySelectorAll("[data-answer-disclosure]")];
  const answerChoices = [...root.querySelectorAll("[data-answer-choice]")];
  const principleLinks = [...root.querySelectorAll("[data-principle-link]")];
  const studyCardList = document.getElementById("study-card-list");
  const cardLocations = new Map();
  const restoreCardOrder = () => {
    for (const [card, marker] of cardLocations) marker.replaceWith(card);
    cardLocations.clear();
    if (studyCardList) studyCardList.hidden = true;
  };
  let activeType = "all";
  const historyAPI = globalThis.ArchitectAnswerHistory;
  const attempts = new Map();
  const viewedDays = new Map();
  const summaries = new Map();
  const publish = (name, detail) => {
    if (typeof CustomEvent === "function") document.dispatchEvent?.(new CustomEvent(name, { detail }));
  };
  let historyStore = null;
  let historyFailure = false;
  const reportHistory = (message, failure = false) => {
    historyFailure = failure;
    if (historyStatus) {
      historyStatus.textContent = message;
      historyStatus.dataset.error = String(failure);
    }
  };
  const uuid = () => globalThis.crypto.randomUUID();
  const metadata = (card) => ({
    itemId: card.dataset.studyId,
    revision: card.dataset.questionRevision,
    correctChoice: card.dataset.correctChoice,
  });
  const canRecord = (card) =>
    Boolean(historyStore && card?.dataset.studyId && card.dataset.questionRevision &&
      ["A", "B"].includes(card.dataset.correctChoice));
  const eventTime = (event) =>
    `${new Date(Date.parse(event.at) - event.offsetMinutes * 60000).toISOString().slice(0, 16).replace("T", " ")}（回答時の現地日時）`;

  const renderHistory = (card, events) => {
    const { itemId, revision } = metadata(card);
    if (!itemId || !revision) return;
    const summary = historyAPI.summarize(events, itemId, revision);
    summaries.set(card, summary);
    const result = card.querySelector("[data-answer-result]");
    const attempt = attempts.get(card);
    const retry = card.querySelector("[data-answer-retry]");
    if (retry) retry.hidden = !attempt?.answered;
    if (result) {
      const state = summary.priority ? "重点復習" : summary.review ? "要復習" : summary.unanswered ? "未回答" : "回答済み";
      const latest = summary.latest;
      const latestText = latest
        ? ` 最終回答：${eventTime(latest)}・${latest.correct ? "正解" : "不正解"}（${latest.independent ? "独力" : "答え確認後"}）。`
        : "";
      const outcome = attempt?.answer
        ? `今回：${attempt.answer.choice}を選択 → ${attempt.answer.correct ? "正解" : "不正解"}。${attempt.answer.independent ? "独力の初回回答" : "答え確認後の回答（復習判定の対象外）"}。 `
        : "";
      const oldText = summary.oldAnswers.length
        ? ` 旧版の回答${summary.oldAnswers.length}件は今回の判定に含めません。`
        : "";
      result.textContent = `${outcome}${state}。独力の連続誤答：${summary.wrongStreak}回。${summary.review ? `復習解除まで別日の独力正解：${summary.recoveryDays}/2日。` : ""}${latestText}${oldText}`;
      result.dataset.reviewState = summary.priority ? "priority" : summary.review ? "review" : "none";
    }
    const list = card.querySelector("[data-answer-history-list]");
    if (list) {
      const entries = [...summary.answers, ...summary.oldAnswers].sort((a, b) => historyAPI.compareEvents(b, a));
      const rows = entries.slice(0, 100).map((event) => {
        const row = document.createElement("li");
        const version = event.revision === revision ? "現在版" : "旧版・集計対象外";
        row.textContent = `${eventTime(event)}｜${event.choice} → ${event.correct ? "正解" : "不正解"}（当時の正解：${event.correctChoice}）｜${event.independent ? "独力" : "答え確認後"}｜${version}`;
        return row;
      });
      if (!rows.length || entries.length > 100) {
        const row = document.createElement("li");
        row.textContent = rows.length ? `最新100件を表示しています。全${entries.length}件はバックアップに含まれます。` : "まだ回答履歴はありません。";
        rows.push(row);
      }
      list.replaceChildren(...rows);
    }
  };

  const resetStaleAttempts = () => {
    if (!historyAPI) return;
    const today = historyAPI.localDay(new Date());
    for (const [card, attempt] of attempts) {
      if (attempt.day !== today) attempts.delete(card);
    }
  };

  const refreshHistory = () => {
    if (!historyStore) return false;
    try {
      const events = historyStore.read();
      resetStaleAttempts();
      for (const card of cards) renderHistory(card, events);
      publish("architect:history", null);
      return true;
    } catch (error) { reportHistory(error.message, true); return false; }
  };

  if (historyAPI) {
    try {
      historyStore = historyAPI.createStore({ storage: window.localStorage, uuid, sessionId: uuid() });
      refreshHistory();
    } catch (error) { reportHistory(`回答履歴を利用できません。${error.message}`, true); }
  } else if (reviewFilter) {
    reportHistory("回答履歴の機能を読み込めませんでした。再読み込みしてください。", true);
  }

  const markViewed = (card) => {
    if (!canRecord(card)) return;
    // A failed persistence write must not turn already-seen material into an
    // independent answer later in this page session when storage recovers.
    const days = viewedDays.get(card) ?? new Set();
    days.add(historyAPI.localDay(new Date()));
    viewedDays.set(card, days);
    const { itemId, revision } = metadata(card);
    try { historyStore.view(itemId, revision); }
    catch (error) { reportHistory(error.message, true); }
  };

  const recordChoice = (choice) => {
    const card = choice.closest(".principle-card");
    if (!canRecord(card)) return;
    if ((card.querySelector("[data-answer-history]")?.open && summaries.get(card)?.hasHistory) ||
        viewedDays.get(card)?.has(historyAPI.localDay(new Date()))) markViewed(card);
    let attempt = attempts.get(card);
    const day = historyAPI.localDay(new Date());
    if (!attempt || attempt.day !== day) { attempt = { id: uuid(), answered: false, day }; attempts.set(card, attempt); }
    if (attempt.answered) return;
    // Lock before saving: repeated clicks never create another answer, even if storage fails.
    attempt.answered = true;
    const retry = card.querySelector("[data-answer-retry]");
    if (retry) retry.hidden = false;
    try {
      attempt.answer = historyStore.answer({ ...metadata(card), attemptId: attempt.id,
        choice: choice.dataset.answerChoice });
      refreshHistory();
      publish("architect:answer", { ...metadata(card), answer: attempt.answer });
      if (!historyFailure) reportHistory("回答をこのブラウザに保存しました。表示中のカードは、絞込みを操作するまで移動・非表示にしません。");
    } catch (error) {
      reportHistory(error.message, true);
      const result = card.querySelector("[data-answer-result]");
      if (result) result.textContent = "今回の回答は保存されていません。答えを確認後、保存制限を確認してください。";
    }
  };

  const coverageTiersByFilter = new Map([
    ["all", [1, 2, 3]],
    ["core-only", [1]],
    ["standard-only", [2]],
    ["advanced-only", [3]],
    ["core+standard", [1, 2]],
  ]);

  const normalize = (value) =>
    value.normalize("NFKC").toLocaleLowerCase("ja-JP").trim();

  const matchesCoverageFilter = (filter, tier) =>
    coverageTiersByFilter.get(filter)?.includes(tier) ?? false;

  const updateBulkAnswerButton = (answersOpen) => {
    for (const button of answerToggleButtons) {
      button.textContent = answersOpen
        ? "表示中の答えをすべて閉じる"
        : "表示中の答えをすべて開く";
      button.setAttribute("aria-pressed", String(answersOpen));
    }
  };

  const visibleAnswerDisclosures = () =>
    disclosures.filter((disclosure) => {
      const card = disclosure.closest(".principle-card");
      return card && !card.hidden;
    });

  const syncChoiceExpansion = (disclosure) => {
    const expanded = String(disclosure.open);
    for (const choice of answerChoices) {
      if (choice.getAttribute("aria-controls") === disclosure.id) {
        choice.setAttribute("aria-expanded", expanded);
      }
    }
  };

  const setAnswerOpen = (disclosure, open) => {
    disclosure.open = open;
    syncChoiceExpansion(disclosure);
  };

  const openAnswerForChoice = (choice) => {
    const controlledId = choice.getAttribute("aria-controls");
    const disclosure = controlledId
      ? document.getElementById(controlledId)
      : null;
    if (!disclosure) return;
    if (disclosure.open) markViewed(choice.closest(".principle-card"));
    recordChoice(choice);
    setAnswerOpen(disclosure, true);
    syncBulkAnswerButton();
  };

  const syncBulkAnswerButton = () => {
    const visibleDisclosures = visibleAnswerDisclosures();
    updateBulkAnswerButton(
      visibleDisclosures.length > 0 &&
        visibleDisclosures.every((disclosure) => disclosure.open),
    );
  };

  const closeAnswers = () => {
    for (const disclosure of disclosures) {
      setAnswerOpen(disclosure, false);
    }
    updateBulkAnswerButton(false);
  };

  const updatePrintPositions = () => {
    let position = 0;
    for (const card of root.querySelectorAll(".principle-card")) {
      const label = card.querySelector("[data-print-position]");
      if (!label) {
        continue;
      }
      label.textContent = card.hidden ? "" : `問${++position}`;
    }
  };

  const canonicalizeFragment = () => {
    const hash = window.location?.hash || "";
    if (!hash.startsWith("#") || typeof document.getElementById !== "function") {
      return;
    }
    let identifier;
    try {
      identifier = decodeURIComponent(hash.slice(1));
    } catch {
      return;
    }
    const legacyAnchor = document.getElementById(identifier);
    const canonical = legacyAnchor?.dataset?.canonicalFragment;
    if (!canonical || canonical === identifier) {
      return;
    }
    window.history?.replaceState?.(null, "", `#${encodeURIComponent(canonical)}`);
    document.getElementById(canonical)?.scrollIntoView();
  };

  closeAnswers();

  for (const disclosure of disclosures) {
    disclosure.querySelector("summary")?.addEventListener("click", () => {
      if (!disclosure.open) markViewed(disclosure.closest(".principle-card"));
    });
    disclosure.addEventListener("toggle", () => {
      if (disclosure.open) markViewed(disclosure.closest(".principle-card"));
      syncChoiceExpansion(disclosure);
      syncBulkAnswerButton();
    });
  }

  for (const choice of answerChoices) {
    choice.addEventListener("click", () => openAnswerForChoice(choice));
    // Native buttons synthesize click for Enter/Space. A keydown handler double-counts.
  }

  for (const card of cards) {
    const explanationSearch = card.querySelector('[data-research-search="explanation"]');
    explanationSearch?.addEventListener("click", () => markViewed(card));
    explanationSearch?.addEventListener("auxclick", () => markViewed(card));
    card.querySelector("[data-answer-retry]")?.addEventListener("click", () => {
      const historyPanel = card.querySelector("[data-answer-history]");
      if (historyPanel?.open && summaries.get(card)?.hasHistory) markViewed(card);
      if (historyPanel) historyPanel.open = false;
      for (const disclosure of disclosures) {
        if (disclosure.closest(".principle-card") === card) {
          if (disclosure.open) markViewed(card);
          setAnswerOpen(disclosure, false);
        }
      }
      if (historyStore) attempts.set(card, { id: uuid(), answered: false, day: historyAPI.localDay(new Date()) });
      refreshHistory();
      syncBulkAnswerButton();
      if (!historyFailure) reportHistory("新しい試行を開始しました。今日すでに答えを確認した問題は、答え確認後の回答として記録します。");
    });
    const historyPanel = card.querySelector("[data-answer-history]");
    historyPanel?.querySelector("summary")?.addEventListener("click", () => {
      if (!historyPanel.open && summaries.get(card)?.hasHistory) markViewed(card);
    });
    historyPanel?.addEventListener("toggle", (event) => {
      if (event.currentTarget.open && summaries.get(card)?.hasHistory) markViewed(card);
    });
  }

  for (const button of answerToggleButtons) button.addEventListener("click", () => {
    const visibleDisclosures = visibleAnswerDisclosures();
    const shouldOpen =
      visibleDisclosures.length > 0 &&
      visibleDisclosures.some((disclosure) => !disclosure.open);
    for (const disclosure of visibleDisclosures) {
      if (shouldOpen) markViewed(disclosure.closest(".principle-card"));
      setAnswerOpen(disclosure, shouldOpen);
    }
    updateBulkAnswerButton(shouldOpen);
  });

  const applyFilters = () => {
    restoreCardOrder();
    closeAnswers();
    const query = normalize(search.value);
    const activeProgress = progress.value;
    const activeSourceKind = sourceKind.value;
    const activeCoverage = coverage.value;
    let count = 0;

    for (const card of cards) {
      const matchesQuery = !query || normalize(card.dataset.search || "").includes(query);
      const matchesType = activeType === "all" || card.dataset.type === activeType;
      const matchesProgress =
        activeProgress === "all" || card.dataset.progress === activeProgress;
      const sourceKinds = (card.dataset.sourceKind || "").split(/\s+/).filter(Boolean);
      const matchesSourceKind =
        activeSourceKind === "all" || sourceKinds.includes(activeSourceKind);
      const coverageTier = Number(card.dataset.coverageTier);
      const matchesCoverage =
        Number.isInteger(coverageTier) &&
        matchesCoverageFilter(activeCoverage, coverageTier);
      const visible =
        matchesQuery &&
        matchesType &&
        matchesProgress &&
        matchesSourceKind &&
        matchesCoverage &&
        (!reviewFilter || reviewFilter.value === "all" ||
          (summaries.has(card) && historyAPI.matchesFilter(summaries.get(card), reviewFilter.value)));
      card.hidden = !visible;
      count += visible ? 1 : 0;
    }

    updateVisibility(count);
    publish("architect:filters", null);
  };

  // One visibility path for catalogue filters and the finite study set. Never
  // move a card after grading: navigation happens only on an explicit action.
  const updateVisibility = (count) => {
    for (const section of sections) {
      section.hidden = !section.querySelector(".principle-card:not([hidden])");
    }
    for (const group of groups) {
      group.hidden = !group.querySelector("[data-catalog-section]:not([hidden])");
    }
    for (const label of document.querySelectorAll("[data-count-for]")) {
      const container = document.getElementById(label.dataset.countFor);
      if (!container) continue;
      const shown = container.querySelectorAll(".principle-card:not([hidden])").length;
      const total = Number(label.dataset.totalCount);
      label.textContent = shown === total ? `${total}件` : `${shown} / 全${total}件`;
    }
    updatePrintPositions();
    visibleCount.textContent = String(count);
    empty.hidden = count !== 0;
    syncBulkAnswerButton();
  };

  canonicalizeFragment();
  window.addEventListener("pageshow", closeAnswers);
  window.addEventListener("hashchange", () => {
    closeAnswers();
    canonicalizeFragment();
  });
  // The print stylesheet includes questions only, never the answer content.
  window.addEventListener("beforeprint", updatePrintPositions);

  for (const link of principleLinks) {
    link.addEventListener("click", closeAnswers);
  }

  search.addEventListener("input", applyFilters);
  progress.addEventListener("change", applyFilters);
  sourceKind.addEventListener("change", applyFilters);
  coverage.addEventListener("change", applyFilters);
  reviewFilter?.addEventListener("change", () => { refreshHistory(); applyFilters(); });
  window.addEventListener("storage", (event) => {
    if (event.key === null || event.key?.startsWith(historyAPI?.PREFIX)) refreshHistory();
  });
  window.addEventListener("focus", () => {
    for (const disclosure of disclosures) {
      if (disclosure.open) markViewed(disclosure.closest(".principle-card"));
    }
    for (const card of cards) {
      if (card.querySelector("[data-answer-history]")?.open && summaries.get(card)?.hasHistory) markViewed(card);
    }
    refreshHistory();
  });

  historyExport?.addEventListener("click", () => {
    if (!historyStore) { reportHistory("回答履歴を利用できないため、バックアップできません。", true); return; }
    let url;
    try {
      url = URL.createObjectURL(new Blob([historyStore.exportBackup()], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `steel-answer-history-${historyAPI.localDay(new Date())}.json`;
      link.click();
      reportHistory("回答履歴のバックアップをダウンロードしました。個人の学習記録として安全に保管してください。");
    } catch (error) { reportHistory(`バックアップできません。${error.message}`, true); }
    finally { if (url) setTimeout(() => URL.revokeObjectURL(url), 1000); }
  });
  historyImport?.addEventListener("change", async () => {
    const file = historyImport.files?.[0];
    if (!file) return;
    try {
      if (!historyStore) throw new Error("回答履歴を利用できません。");
      if (file.size > historyAPI.MAX_IMPORT_BYTES) throw new Error("履歴ファイルは20 MB以下にしてください。");
      const added = historyStore.importBackup(await file.text());
      if (refreshHistory()) reportHistory(`${added}件の履歴を追加しました。同じ履歴は重複せず、既存の記録は保持しました。絞込みを操作すると復習対象が更新されます。`);
    } catch (error) { refreshHistory(); reportHistory(error.message, true); }
    finally { historyImport.value = ""; }
  });

  for (const button of typeButtons) {
    button.addEventListener("click", () => {
      activeType = button.dataset.filterType || "all";
      for (const candidate of typeButtons) {
        const pressed = candidate === button;
        candidate.classList.toggle("is-active", pressed);
        candidate.setAttribute("aria-pressed", String(pressed));
      }
      applyFilters();
    });
  }

  reset.addEventListener("click", () => {
    search.value = "";
    progress.value = "all";
    sourceKind.value = "all";
    coverage.value = "all";
    if (reviewFilter) reviewFilter.value = "all";
    activeType = "all";
    for (const button of typeButtons) {
      const pressed = button.dataset.filterType === "all";
      button.classList.toggle("is-active", pressed);
      button.setAttribute("aria-pressed", String(pressed));
    }
    applyFilters();
    search.focus();
  });

  globalThis.ArchitectCatalog = {
    cards, root, closeAnswers, refreshHistory, applyFilters,
    readEvents() {
      if (!historyStore) throw new Error("回答履歴を利用できません。保存設定を確認してください。");
      return historyStore.read();
    },
    showCards(itemIds, { ordered = false, preserveAnswers = false } = {}) {
      if (!preserveAnswers) closeAnswers();
      restoreCardOrder();
      if (ordered && studyCardList) {
        const byId = new Map(cards.map((card) => [card.dataset.studyId, card]));
        for (const itemId of new Set(itemIds)) {
          const card = byId.get(itemId);
          if (!card) continue;
          const marker = document.createComment("study-card-location");
          card.before(marker);
          cardLocations.set(card, marker);
          studyCardList.append(card);
        }
        studyCardList.hidden = false;
      }
      refreshHistory();
      const visible = new Set(itemIds);
      for (const card of cards) card.hidden = !visible.has(card.dataset.studyId);
      updateVisibility(cards.filter((card) => !card.hidden).length);
    },
  };
})();
