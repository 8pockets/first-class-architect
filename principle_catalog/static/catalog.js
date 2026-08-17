(() => {
  "use strict";

  const root = document.querySelector("[data-catalog-root]");
  const search = document.querySelector("#catalog-search");
  const progress = document.querySelector("#progress-filter");
  const sourceKind = document.querySelector("#source-kind-filter");
  const coverage = document.querySelector("#coverage-filter");
  const toggleVisibleAnswers = document.querySelector("#toggle-visible-answers");
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
  let activeType = "all";
  let bulkAnswersOpen = false;

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
    if (!toggleVisibleAnswers) return;
    toggleVisibleAnswers.textContent = answersOpen
      ? "表示中の答えをすべて閉じる"
      : "表示中の答えをすべて開く";
    toggleVisibleAnswers.setAttribute("aria-pressed", String(answersOpen));
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
    if (!bulkAnswersOpen) {
      for (const candidate of disclosures) {
        if (candidate !== disclosure) setAnswerOpen(candidate, false);
      }
    }
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
    bulkAnswersOpen = false;
    updateBulkAnswerButton(false);
  };

  const updatePrintPositions = () => {
    let position = 0;
    for (const card of cards) {
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
    disclosure.addEventListener("toggle", () => {
      syncChoiceExpansion(disclosure);
      if (bulkAnswersOpen) return;
      if (disclosure.open) {
        for (const candidate of disclosures) {
          if (candidate !== disclosure) setAnswerOpen(candidate, false);
        }
      }
      syncBulkAnswerButton();
    });

    disclosure.querySelector("summary")?.addEventListener("click", () => {
      bulkAnswersOpen = false;
      updateBulkAnswerButton(false);
      for (const candidate of disclosures) {
        if (candidate !== disclosure) setAnswerOpen(candidate, false);
      }
    });
  }

  for (const choice of answerChoices) {
    choice.addEventListener("click", () => openAnswerForChoice(choice));
    choice.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openAnswerForChoice(choice);
    });
  }

  toggleVisibleAnswers?.addEventListener("click", () => {
    const visibleDisclosures = visibleAnswerDisclosures();
    const shouldOpen =
      visibleDisclosures.length > 0 &&
      visibleDisclosures.some((disclosure) => !disclosure.open);
    bulkAnswersOpen = shouldOpen;
    for (const disclosure of visibleDisclosures) {
      setAnswerOpen(disclosure, shouldOpen);
    }
    updateBulkAnswerButton(shouldOpen);
  });

  const applyFilters = () => {
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
        matchesCoverage;
      card.hidden = !visible;
      count += visible ? 1 : 0;
    }

    for (const section of sections) {
      section.hidden = !section.querySelector(".principle-card:not([hidden])");
    }

    for (const group of groups) {
      group.hidden = !group.querySelector("[data-catalog-section]:not([hidden])");
    }

    updatePrintPositions();
    visibleCount.textContent = String(count);
    empty.hidden = count !== 0;
  };

  canonicalizeFragment();
  window.addEventListener("pageshow", closeAnswers);
  window.addEventListener("hashchange", () => {
    closeAnswers();
    canonicalizeFragment();
  });
  window.addEventListener("beforeprint", updatePrintPositions);

  for (const link of principleLinks) {
    link.addEventListener("click", closeAnswers);
  }

  search.addEventListener("input", applyFilters);
  progress.addEventListener("change", applyFilters);
  sourceKind.addEventListener("change", applyFilters);
  coverage.addEventListener("change", applyFilters);

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
    activeType = "all";
    for (const button of typeButtons) {
      const pressed = button.dataset.filterType === "all";
      button.classList.toggle("is-active", pressed);
      button.setAttribute("aria-pressed", String(pressed));
    }
    applyFilters();
    search.focus();
  });
})();
