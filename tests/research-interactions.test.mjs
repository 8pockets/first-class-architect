import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const script = readFileSync(
  new URL("../principle_catalog/static/research.js", import.meta.url),
  "utf8",
);

class FakeElement extends EventTarget {
  constructor({ dataset = {}, id = "", value = "" } = {}) {
    super();
    this.dataset = dataset;
    this.id = id;
    this.value = value;
    this.hidden = false;
    this.open = false;
    this.textContent = "";
  }

  querySelector(selector) {
    if (selector === ".research-card:not([hidden])") {
      return this.cards?.find((card) => !card.hidden) ?? null;
    }
    if (selector === "summary") return this.summary ?? null;
    return null;
  }

  closest(selector) {
    if (selector === ".research-card") return this.card ?? null;
    return null;
  }
}

const bootResearchPage = () => {
  const cards = [
    new FakeElement({ dataset: { researchCoverageTier: "1" } }),
    new FakeElement({ dataset: { researchCoverageTier: "2" } }),
    new FakeElement({ dataset: { researchCoverageTier: "3" } }),
  ];
  const disclosures = cards.map((card) => {
    const disclosure = new FakeElement();
    disclosure.open = true;
    disclosure.card = card;
    disclosure.summary = new FakeElement();
    return disclosure;
  });
  const sections = cards.map((card, index) => {
    const section = new FakeElement({ id: `research-section-${index + 1}` });
    section.cards = [card];
    return section;
  });
  const navLinks = sections.map(
    (section) =>
      new FakeElement({
        dataset: { researchNavTarget: section.id },
      }),
  );
  const root = {
    querySelectorAll: (selector) => {
      if (selector === ".research-card") return cards;
      if (selector === "[data-research-section]") return sections;
      if (selector === "[data-research-answer-disclosure]") return disclosures;
      return [];
    },
  };
  const coverage = new FakeElement({ value: "all" });
  const visibleCount = new FakeElement();
  const document = {
    querySelector: (selector) =>
      new Map([
        ["[data-research-catalog-root]", root],
        ["#research-coverage-filter", coverage],
        ["#research-visible-count", visibleCount],
      ]).get(selector) ?? null,
    querySelectorAll: (selector) =>
      selector === "[data-research-nav-target]" ? navLinks : [],
  };

  vm.runInNewContext(script, { document, Event });
  return { cards, coverage, disclosures, navLinks, sections, visibleCount };
};

test("research coverage filter exposes all, each tier, and foundation plus standard", () => {
  const { cards, coverage, navLinks, sections, visibleCount } = bootResearchPage();

  assert.deepEqual(cards.map(({ hidden }) => hidden), [false, false, false]);
  assert.equal(visibleCount.textContent, "3");

  const expected = new Map([
    ["core-only", [false, true, true]],
    ["standard-only", [true, false, true]],
    ["advanced-only", [true, true, false]],
    ["core+standard", [false, false, true]],
    ["all", [false, false, false]],
  ]);
  for (const [filter, hidden] of expected) {
    coverage.value = filter;
    coverage.dispatchEvent(new Event("change"));
    assert.deepEqual(cards.map((card) => card.hidden), hidden);
    assert.deepEqual(sections.map((section) => section.hidden), hidden);
    assert.deepEqual(navLinks.map((link) => link.hidden), hidden);
    assert.equal(
      visibleCount.textContent,
      String(hidden.filter((isHidden) => !isHidden).length),
    );
  }
});

test("provisional answers start closed, stay single-open, and close on filtering", () => {
  const { coverage, disclosures } = bootResearchPage();

  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);

  disclosures[0].open = true;
  disclosures[0].dispatchEvent(new Event("toggle"));
  disclosures[1].open = true;
  disclosures[1].dispatchEvent(new Event("toggle"));
  assert.deepEqual(disclosures.map(({ open }) => open), [false, true, false]);

  coverage.value = "core-only";
  coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);
});
