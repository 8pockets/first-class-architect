(() => {
  "use strict";

  const root = document.querySelector("[data-research-catalog-root]");
  const coverage = document.querySelector("#research-coverage-filter");
  const visibleCount = document.querySelector("#research-visible-count");
  if (!root || !coverage || !visibleCount) return;

  const cards = [...root.querySelectorAll(".research-card")];
  const sections = [...root.querySelectorAll("[data-research-section]")];
  const navLinks = [...document.querySelectorAll("[data-research-nav-target]")];
  const sectionsById = new Map(sections.map((section) => [section.id, section]));
  const disclosures = [
    ...root.querySelectorAll("[data-research-answer-disclosure]"),
  ];
  const tiersByFilter = new Map([
    ["all", [1, 2, 3]],
    ["core-only", [1]],
    ["standard-only", [2]],
    ["advanced-only", [3]],
    ["core+standard", [1, 2]],
  ]);

  const closeAnswers = () => {
    for (const disclosure of disclosures) disclosure.open = false;
  };

  const applyCoverageFilter = () => {
    closeAnswers();
    const acceptedTiers = tiersByFilter.get(coverage.value) ?? [];
    let count = 0;
    for (const card of cards) {
      const tier = Number(card.dataset.researchCoverageTier);
      card.hidden = !acceptedTiers.includes(tier);
      if (!card.hidden) count += 1;
    }
    for (const section of sections) {
      section.hidden = !section.querySelector(".research-card:not([hidden])");
    }
    for (const link of navLinks) {
      const section = sectionsById.get(link.dataset.researchNavTarget);
      link.hidden = !section || section.hidden;
    }
    visibleCount.textContent = String(count);
  };

  closeAnswers();
  for (const disclosure of disclosures) {
    disclosure.addEventListener("toggle", () => {
      if (!disclosure.open) return;
      for (const candidate of disclosures) {
        if (candidate !== disclosure) candidate.open = false;
      }
    });
  }
  coverage.addEventListener("change", applyCoverageFilter);
  applyCoverageFilter();
})();
