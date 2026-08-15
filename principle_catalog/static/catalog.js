(() => {
  "use strict";

  const root = document.querySelector("[data-catalog-root]");
  const search = document.querySelector("#catalog-search");
  const progress = document.querySelector("#progress-filter");
  const sourceKind = document.querySelector("#source-kind-filter");
  const coverage = document.querySelector("#coverage-filter");
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
  let activeType = "all";

  const normalize = (value) =>
    value.normalize("NFKC").toLocaleLowerCase("ja-JP").trim();

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

  const applyFilters = () => {
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
        activeCoverage === "all" ||
        (Number.isInteger(coverageTier) && coverageTier <= Number(activeCoverage));
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
  window.addEventListener("hashchange", canonicalizeFragment);
  window.addEventListener("beforeprint", updatePrintPositions);

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
