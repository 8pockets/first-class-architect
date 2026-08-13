(() => {
  "use strict";

  const root = document.querySelector("[data-catalog-root]");
  const search = document.querySelector("#catalog-search");
  const progress = document.querySelector("#progress-filter");
  const typeButtons = [...document.querySelectorAll("[data-filter-type]")];
  const reset = document.querySelector("#reset-filters");
  const visibleCount = document.querySelector("#visible-count");
  const empty = document.querySelector("#empty-state");

  if (!root || !search || !progress || !reset || !visibleCount || !empty) {
    return;
  }

  const cards = [...root.querySelectorAll(".principle-card")];
  const sections = [...root.querySelectorAll("[data-catalog-section]")];
  const disclosures = [...root.querySelectorAll("[data-disclosure]")];
  const principleLinks = [...root.querySelectorAll("[data-principle-link]")];
  let activeType = "all";

  const normalize = (value) =>
    value.normalize("NFKC").toLocaleLowerCase("ja-JP").trim();

  const closeDisclosures = () => {
    for (const disclosure of disclosures) {
      disclosure.open = false;
    }
  };

  const applyFilters = () => {
    closeDisclosures();
    const query = normalize(search.value);
    const activeProgress = progress.value;
    let count = 0;

    for (const card of cards) {
      const matchesQuery = !query || normalize(card.dataset.search || "").includes(query);
      const matchesType = activeType === "all" || card.dataset.type === activeType;
      const matchesProgress =
        activeProgress === "all" || card.dataset.progress === activeProgress;
      const visible = matchesQuery && matchesType && matchesProgress;
      card.hidden = !visible;
      count += visible ? 1 : 0;
    }

    for (const section of sections) {
      section.hidden = !section.querySelector(".principle-card:not([hidden])");
    }

    visibleCount.textContent = String(count);
    empty.hidden = count !== 0;
  };

  closeDisclosures();
  window.addEventListener("pageshow", closeDisclosures);
  window.addEventListener("hashchange", closeDisclosures);

  for (const disclosure of disclosures) {
    disclosure.addEventListener("toggle", () => {
      if (!disclosure.open) {
        return;
      }
      for (const candidate of disclosures) {
        if (candidate !== disclosure) {
          candidate.open = false;
        }
      }
    });
  }

  for (const link of principleLinks) {
    link.addEventListener("click", closeDisclosures);
  }

  search.addEventListener("input", applyFilters);
  progress.addEventListener("change", applyFilters);

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
