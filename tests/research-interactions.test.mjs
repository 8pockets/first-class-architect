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
    this.attributes = new Map();
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
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
  const disclosures = cards.map((card, index) => {
    const disclosure = new FakeElement({ id: `research-answer-${index + 1}` });
    disclosure.open = true;
    disclosure.card = card;
    disclosure.summary = new FakeElement();
    return disclosure;
  });
  const answerChoices = cards.flatMap((_card, index) =>
    ["A", "B"].map(() => {
      const choice = new FakeElement();
      choice.setAttribute("aria-controls", disclosures[index].id);
      choice.setAttribute("aria-expanded", "false");
      return choice;
    }),
  );
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
      if (selector === "[data-research-answer-choice]") return answerChoices;
      return [];
    },
  };
  const coverage = new FakeElement({ value: "all" });
  const visibleCount = new FakeElement();
  const elementsById = new Map(
    disclosures.map((disclosure) => [disclosure.id, disclosure]),
  );
  const document = {
    querySelector: (selector) =>
      new Map([
        ["[data-research-catalog-root]", root],
        ["#research-coverage-filter", coverage],
        ["#research-visible-count", visibleCount],
      ]).get(selector) ?? null,
    querySelectorAll: (selector) =>
      selector === "[data-research-nav-target]" ? navLinks : [],
    getElementById: (identifier) => elementsById.get(identifier) ?? null,
  };

  vm.runInNewContext(script, { document, Event });
  return {
    answerChoices,
    cards,
    coverage,
    disclosures,
    navLinks,
    sections,
    visibleCount,
  };
};

const pressChoice = (choice, key) => {
  const event = new Event("keydown", { cancelable: true });
  Object.defineProperty(event, "key", { value: key });
  choice.dispatchEvent(event);
  return event;
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

test("choosing A or B opens provisional or pending content and stays open on repeat", () => {
  const { answerChoices, disclosures } = bootResearchPage();

  answerChoices[0].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, false]);
  assert.deepEqual(
    answerChoices.slice(0, 2).map((choice) => choice.getAttribute("aria-expanded")),
    ["true", "true"],
  );

  answerChoices[4].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, true]);
  assert.deepEqual(
    answerChoices.map((choice) => choice.getAttribute("aria-expanded")),
    ["false", "false", "false", "false", "true", "true"],
  );

  answerChoices[4].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, true]);
});

test("Enter and Space open provisional or pending content without browser click synthesis", () => {
  const { answerChoices, disclosures } = bootResearchPage();

  const enterEvent = pressChoice(answerChoices[0], "Enter");
  assert.equal(enterEvent.defaultPrevented, true);
  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, false]);

  const spaceEvent = pressChoice(answerChoices[4], " ");
  assert.equal(spaceEvent.defaultPrevented, true);
  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, true]);
});
