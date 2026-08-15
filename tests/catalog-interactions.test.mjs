import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const script = readFileSync(
  new URL("../principle_catalog/static/catalog.js", import.meta.url),
  "utf8",
);

class FakeElement extends EventTarget {
  constructor({ dataset = {}, value = "" } = {}) {
    super();
    this.dataset = dataset;
    this.value = value;
    this.hidden = false;
    this.textContent = "";
    this.attributes = new Map();
    this.classList = {
      toggle: () => {},
    };
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  querySelector(selector) {
    if (selector === "[data-print-position]") return this.printPosition ?? null;
    return null;
  }

  focus() {}

  scrollIntoView() {
    this.scrolledIntoView = true;
  }
}

const bootCatalog = ({ catalogCards } = {}) => {
  const defaultCards = [
    new FakeElement({
      dataset: {
        search: "解説だけの語",
        type: "principle",
        progress: "unstarted",
        sourceKind: "pdf prior_question_table",
        coverageTier: "1",
      },
    }),
    new FakeElement({
      dataset: {
        search: "座屈の語",
        type: "principle",
        progress: "learning",
        sourceKind: "pdf teaching_material",
        coverageTier: "2",
      },
    }),
    new FakeElement({
      dataset: {
        search: "溶接の語",
        type: "rule",
        progress: "mastered",
        sourceKind: "pdf law teaching_material",
        coverageTier: "3",
      },
    }),
  ];
  const cards = catalogCards ?? defaultCards;
  cards.forEach((card, index) => {
    card.printNumber = `Q${String(index + 1).padStart(3, "0")}`;
  });
  const printPositions = cards.map((card, index) => {
    const position = new FakeElement();
    position.textContent = `問${index + 1}`;
    card.printPosition = position;
    return position;
  });
  const sections = catalogCards
    ? [
        {
          hidden: false,
          querySelector: () => cards.find((card) => !card.hidden) ?? null,
        },
      ]
    : [
        {
          hidden: false,
          querySelector: () => cards.slice(0, 2).find((card) => !card.hidden) ?? null,
        },
        {
          hidden: false,
          querySelector: () => cards.slice(2).find((card) => !card.hidden) ?? null,
        },
      ];
  const groups = sections.map((section) => ({
    hidden: false,
    querySelector: () => (section.hidden ? null : section),
  }));
  const root = {
    querySelectorAll: (selector) => {
      if (selector === ".principle-card") return cards;
      if (selector === "[data-catalog-section]") return sections;
      if (selector === "[data-catalog-group]") return groups;
      return [];
    },
  };
  const search = new FakeElement();
  const progress = new FakeElement({ value: "all" });
  const sourceKind = new FakeElement({ value: "all" });
  const coverage = new FakeElement({ value: "all" });
  const reset = new FakeElement();
  const visibleCount = new FakeElement();
  const empty = new FakeElement();
  const typeButtons = [
    new FakeElement({ dataset: { filterType: "all" } }),
    new FakeElement({ dataset: { filterType: "principle" } }),
  ];
  const elements = new Map([
    ["[data-catalog-root]", root],
    ["#catalog-search", search],
    ["#progress-filter", progress],
    ["#source-kind-filter", sourceKind],
    ["#coverage-filter", coverage],
    ["#reset-filters", reset],
    ["#visible-count", visibleCount],
    ["#empty-state", empty],
  ]);
  const legacyAnchor = new FakeElement({
    dataset: { canonicalFragment: "structure.steel.compression-member-slenderness" },
  });
  const canonicalCard = new FakeElement();
  const elementsById = new Map([
    ["S-K6-18-SLENDERNESS", legacyAnchor],
    ["structure.steel.compression-member-slenderness", canonicalCard],
  ]);
  const document = {
    querySelector: (selector) => elements.get(selector) ?? null,
    querySelectorAll: (selector) =>
      selector === "[data-filter-type]" ? typeButtons : [],
    getElementById: (identifier) => elementsById.get(identifier) ?? null,
  };
  const window = new EventTarget();
  window.location = { hash: "" };
  window.history = {
    replacement: null,
    replaceState: (_state, _title, replacement) => {
      window.history.replacement = replacement;
    },
  };

  vm.runInNewContext(script, { document, Event, window });

  return {
    cards,
    groups,
    canonicalCard,
    coverage,
    printPositions,
    progress,
    reset,
    search,
    sourceKind,
    typeButtons,
    visibleCount,
    window,
  };
};

test("search includes always-visible explanation text", () => {
  const { cards, search } = bootCatalog();
  search.value = "解説だけの語";

  search.dispatchEvent(new Event("input"));

  assert.equal(cards[0].hidden, false);
});

test("filtering hides nonmatches without renumbering or reordering cards", () => {
  const { cards, search } = bootCatalog();
  const originalCards = [...cards];
  const originalNumbers = cards.map(({ printNumber }) => printNumber);
  search.value = "溶接";

  search.dispatchEvent(new Event("input"));

  assert.deepEqual(cards.map(({ hidden }) => hidden), [true, true, false]);
  assert.deepEqual(cards, originalCards);
  assert.deepEqual(
    cards.map(({ printNumber }) => printNumber),
    originalNumbers,
  );
});

test("source-kind filtering finds cards by PDF page kind or authority kind", () => {
  const { cards, groups, sourceKind } = bootCatalog();
  sourceKind.value = "law";

  sourceKind.dispatchEvent(new Event("change"));

  assert.deepEqual(cards.map(({ hidden }) => hidden), [true, true, false]);
  assert.deepEqual(groups.map(({ hidden }) => hidden), [true, false]);
});

test("coverage filtering cumulatively includes every tier up to the selected depth", () => {
  const { cards, coverage, visibleCount } = bootCatalog();

  coverage.value = "1";
  coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(cards.map(({ hidden }) => hidden), [false, true, true]);
  assert.equal(visibleCount.textContent, "1");

  coverage.value = "2";
  coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(cards.map(({ hidden }) => hidden), [false, false, true]);
  assert.equal(visibleCount.textContent, "2");

  coverage.value = "all";
  coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(cards.map(({ hidden }) => hidden), [false, false, false]);
  assert.equal(visibleCount.textContent, "3");
});

test("coverage filtering exposes the audited cumulative 32, 74, and 116 card sets", () => {
  const catalogCards = [
    ...Array.from({ length: 32 }, () =>
      new FakeElement({
        dataset: {
          search: "骨格",
          type: "principle",
          progress: "unstarted",
          sourceKind: "pdf",
          coverageTier: "1",
        },
      }),
    ),
    ...Array.from({ length: 42 }, () =>
      new FakeElement({
        dataset: {
          search: "標準",
          type: "rule",
          progress: "unstarted",
          sourceKind: "pdf",
          coverageTier: "2",
        },
      }),
    ),
    ...Array.from({ length: 42 }, () =>
      new FakeElement({
        dataset: {
          search: "発展",
          type: "identification",
          progress: "unstarted",
          sourceKind: "pdf",
          coverageTier: "3",
        },
      }),
    ),
  ];
  const { coverage, visibleCount } = bootCatalog({ catalogCards });

  coverage.value = "1";
  coverage.dispatchEvent(new Event("change"));
  assert.equal(visibleCount.textContent, "32");

  coverage.value = "2";
  coverage.dispatchEvent(new Event("change"));
  assert.equal(visibleCount.textContent, "74");

  coverage.value = "all";
  coverage.dispatchEvent(new Event("change"));
  assert.equal(visibleCount.textContent, "116");
});

test("coverage combines with other filters and reset restores the full printable order", () => {
  const {
    cards,
    coverage,
    printPositions,
    progress,
    reset,
    search,
    sourceKind,
    typeButtons,
    visibleCount,
  } = bootCatalog();
  coverage.value = "2";
  coverage.dispatchEvent(new Event("change"));
  progress.value = "learning";
  progress.dispatchEvent(new Event("change"));
  sourceKind.value = "teaching_material";
  sourceKind.dispatchEvent(new Event("change"));
  typeButtons[1].dispatchEvent(new Event("click"));
  search.value = "座屈";
  search.dispatchEvent(new Event("input"));

  assert.deepEqual(cards.map(({ hidden }) => hidden), [true, false, true]);
  assert.equal(visibleCount.textContent, "1");
  assert.deepEqual(
    printPositions.map(({ textContent }) => textContent),
    ["", "問1", ""],
  );

  reset.dispatchEvent(new Event("click"));
  assert.equal(coverage.value, "all");
  assert.equal(progress.value, "all");
  assert.equal(sourceKind.value, "all");
  assert.deepEqual(cards.map(({ hidden }) => hidden), [false, false, false]);
  assert.equal(visibleCount.textContent, "3");
  assert.deepEqual(
    printPositions.map(({ textContent }) => textContent),
    ["問1", "問2", "問3"],
  );
});

test("filtering gives the printable subset a fresh one-based question position", () => {
  const { printPositions, search } = bootCatalog();
  search.value = "溶接";

  search.dispatchEvent(new Event("input"));

  assert.deepEqual(
    printPositions.map(({ textContent }) => textContent),
    ["", "", "問1"],
  );
});

test("a legacy item fragment is canonicalized after its native anchor resolves", () => {
  const { canonicalCard, window } = bootCatalog();
  window.location.hash = "#S-K6-18-SLENDERNESS";

  window.dispatchEvent(new Event("hashchange"));

  assert.equal(
    window.history.replacement,
    "#structure.steel.compression-member-slenderness",
  );
  assert.equal(canonicalCard.scrolledIntoView, true);
});
