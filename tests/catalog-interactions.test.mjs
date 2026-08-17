import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const script = readFileSync(
  new URL("../principle_catalog/static/catalog.js", import.meta.url),
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
    this.classList = {
      toggle: () => {},
    };
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  querySelector(selector) {
    if (selector === "[data-print-position]") return this.printPosition ?? null;
    if (selector === "summary") return this.summary ?? null;
    return null;
  }

  closest(selector) {
    if (selector === ".principle-card") return this.card ?? null;
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
  const disclosures = cards.map(
    (_card, index) => new FakeElement({ id: `answer-${index + 1}` }),
  );
  const answerChoices = cards.flatMap((card, index) =>
    ["A", "B"].map(() => {
      const choice = new FakeElement();
      choice.card = card;
      choice.setAttribute("aria-controls", disclosures[index].id);
      choice.setAttribute("aria-expanded", "false");
      return choice;
    }),
  );
  const principleLinks = [new FakeElement()];
  disclosures.forEach((disclosure, index) => {
    disclosure.open = true;
    disclosure.card = cards[index];
    disclosure.summary = new FakeElement();
  });
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
      if (selector === "[data-answer-disclosure]") return disclosures;
      if (selector === "[data-answer-choice]") return answerChoices;
      if (selector === "[data-principle-link]") return principleLinks;
      return [];
    },
  };
  const search = new FakeElement();
  const progress = new FakeElement({ value: "all" });
  const sourceKind = new FakeElement({ value: "all" });
  const coverage = new FakeElement({ value: "all" });
  const toggleVisibleAnswers = new FakeElement();
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
    ["#toggle-visible-answers", toggleVisibleAnswers],
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
    ...disclosures.map((disclosure) => [disclosure.id, disclosure]),
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
    answerChoices,
    cards,
    disclosures,
    groups,
    canonicalCard,
    coverage,
    printPositions,
    principleLinks,
    progress,
    reset,
    search,
    sourceKind,
    toggleVisibleAnswers,
    typeButtons,
    visibleCount,
    window,
  };
};

const openAnswer = (disclosure) => {
  disclosure.open = true;
  disclosure.dispatchEvent(new Event("toggle"));
};

const pressChoice = (choice, key) => {
  const event = new Event("keydown", { cancelable: true });
  Object.defineProperty(event, "key", { value: key });
  choice.dispatchEvent(event);
  return event;
};

test("answers start closed and opening one closes the previously open answer", () => {
  const { disclosures } = bootCatalog();

  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);
  openAnswer(disclosures[0]);
  openAnswer(disclosures[1]);

  assert.deepEqual(disclosures.map(({ open }) => open), [false, true, false]);
});

test("choosing A or B opens its answer, closes another, and stays open on repeat", () => {
  const { answerChoices, disclosures } = bootCatalog();

  answerChoices[0].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, false]);
  assert.deepEqual(
    answerChoices.slice(0, 2).map((choice) => choice.getAttribute("aria-expanded")),
    ["true", "true"],
  );

  answerChoices[2].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [false, true, false]);
  assert.deepEqual(
    answerChoices.slice(0, 4).map((choice) => choice.getAttribute("aria-expanded")),
    ["false", "false", "true", "true"],
  );

  answerChoices[2].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [false, true, false]);
});

test("Enter and Space open the controlled answer without browser click synthesis", () => {
  const { answerChoices, disclosures } = bootCatalog();

  const enterEvent = pressChoice(answerChoices[0], "Enter");
  assert.equal(enterEvent.defaultPrevented, true);
  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, false]);

  const spaceEvent = pressChoice(answerChoices[2], " ");
  assert.equal(spaceEvent.defaultPrevented, true);
  assert.deepEqual(disclosures.map(({ open }) => open), [false, true, false]);
});

test("clicking a closed answer closes the current answer before native opening", () => {
  const { disclosures } = bootCatalog();
  openAnswer(disclosures[0]);

  disclosures[1].summary.dispatchEvent(new Event("click"));

  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);

  disclosures[1].open = true;
  disclosures[1].dispatchEvent(new Event("toggle"));
  assert.deepEqual(disclosures.map(({ open }) => open), [false, true, false]);
});

test("the bulk answer button opens and closes only answers on visible cards", () => {
  const { cards, disclosures, toggleVisibleAnswers } = bootCatalog();
  cards[2].hidden = true;

  toggleVisibleAnswers.dispatchEvent(new Event("click"));
  for (const disclosure of disclosures.filter(({ open }) => open)) {
    disclosure.dispatchEvent(new Event("toggle"));
  }

  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, false]);
  assert.equal(toggleVisibleAnswers.textContent, "表示中の答えをすべて閉じる");
  assert.equal(toggleVisibleAnswers.attributes.get("aria-pressed"), "true");

  toggleVisibleAnswers.dispatchEvent(new Event("click"));

  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);
  assert.equal(toggleVisibleAnswers.textContent, "表示中の答えをすべて開く");
  assert.equal(toggleVisibleAnswers.attributes.get("aria-pressed"), "false");
});

test("choosing A or B preserves an explicitly opened bulk answer view", () => {
  const { answerChoices, disclosures, toggleVisibleAnswers } = bootCatalog();
  toggleVisibleAnswers.dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, true]);

  answerChoices[2].dispatchEvent(new Event("click"));

  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, true]);
  assert.equal(toggleVisibleAnswers.textContent, "表示中の答えをすべて閉じる");
  assert.equal(toggleVisibleAnswers.attributes.get("aria-pressed"), "true");
});

test("using an individual answer after bulk open returns to single-answer mode", () => {
  const { disclosures, toggleVisibleAnswers } = bootCatalog();
  toggleVisibleAnswers.dispatchEvent(new Event("click"));
  for (const disclosure of disclosures) {
    disclosure.dispatchEvent(new Event("toggle"));
  }
  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, true]);

  disclosures[1].summary.dispatchEvent(new Event("click"));
  disclosures[1].open = false;
  disclosures[1].dispatchEvent(new Event("toggle"));

  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);
  assert.equal(toggleVisibleAnswers.textContent, "表示中の答えをすべて開く");
  assert.equal(toggleVisibleAnswers.attributes.get("aria-pressed"), "false");

  openAnswer(disclosures[2]);
  openAnswer(disclosures[0]);
  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, false]);
});

test("the bulk button reflects whether every visible answer is currently open", () => {
  const { cards, disclosures, toggleVisibleAnswers } = bootCatalog();
  cards[1].hidden = true;
  cards[2].hidden = true;

  openAnswer(disclosures[0]);
  assert.equal(toggleVisibleAnswers.textContent, "表示中の答えをすべて閉じる");
  assert.equal(toggleVisibleAnswers.attributes.get("aria-pressed"), "true");

  disclosures[0].open = false;
  disclosures[0].dispatchEvent(new Event("toggle"));
  assert.equal(toggleVisibleAnswers.textContent, "表示中の答えをすべて開く");
  assert.equal(toggleVisibleAnswers.attributes.get("aria-pressed"), "false");
});

test("changing any search or filter control closes answers and resets the bulk button", () => {
  const {
    coverage,
    disclosures,
    progress,
    reset,
    search,
    sourceKind,
    toggleVisibleAnswers,
    typeButtons,
  } = bootCatalog();
  const controls = [
    [search, "input"],
    [progress, "change"],
    [sourceKind, "change"],
    [coverage, "change"],
    [typeButtons[1], "click"],
    [reset, "click"],
  ];

  for (const [control, eventName] of controls) {
    openAnswer(disclosures[0]);
    control.dispatchEvent(new Event(eventName));
    assert.equal(disclosures[0].open, false, `${eventName} must close answers`);
    assert.equal(toggleVisibleAnswers.textContent, "表示中の答えをすべて開く");
    assert.equal(toggleVisibleAnswers.attributes.get("aria-pressed"), "false");
  }
});

test("page restoration, hash navigation, and fixed links close every answer", () => {
  const { disclosures, principleLinks, toggleVisibleAnswers, window } = bootCatalog();
  const navigations = [
    [window, "pageshow"],
    [window, "hashchange"],
    [principleLinks[0], "click"],
  ];

  for (const [target, eventName] of navigations) {
    openAnswer(disclosures[1]);
    target.dispatchEvent(new Event(eventName));
    assert.deepEqual(
      disclosures.map(({ open }) => open),
      [false, false, false],
      `${eventName} must close every answer`,
    );
    assert.equal(toggleVisibleAnswers.attributes.get("aria-pressed"), "false");
  }
});

test("search includes closed answer text without opening it", () => {
  const { cards, disclosures, search } = bootCatalog();
  search.value = "解説だけの語";

  search.dispatchEvent(new Event("input"));

  assert.equal(cards[0].hidden, false);
  assert.equal(disclosures[0].open, false);
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

test("coverage filtering can isolate each tier or combine core with standard", () => {
  const { cards, coverage, visibleCount } = bootCatalog();

  coverage.value = "core-only";
  coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(cards.map(({ hidden }) => hidden), [false, true, true]);
  assert.equal(visibleCount.textContent, "1");

  coverage.value = "standard-only";
  coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(cards.map(({ hidden }) => hidden), [true, false, true]);
  assert.equal(visibleCount.textContent, "1");

  coverage.value = "advanced-only";
  coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(cards.map(({ hidden }) => hidden), [true, true, false]);
  assert.equal(visibleCount.textContent, "1");

  coverage.value = "core+standard";
  coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(cards.map(({ hidden }) => hidden), [false, false, true]);
  assert.equal(visibleCount.textContent, "2");

  coverage.value = "all";
  coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(cards.map(({ hidden }) => hidden), [false, false, false]);
  assert.equal(visibleCount.textContent, "3");
});

test("coverage filtering exposes the audited 32, 42, 42, 74, and 116 card sets", () => {
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

  coverage.value = "core-only";
  coverage.dispatchEvent(new Event("change"));
  assert.equal(visibleCount.textContent, "32");

  coverage.value = "standard-only";
  coverage.dispatchEvent(new Event("change"));
  assert.equal(visibleCount.textContent, "42");

  coverage.value = "advanced-only";
  coverage.dispatchEvent(new Event("change"));
  assert.equal(visibleCount.textContent, "42");

  coverage.value = "core+standard";
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
  coverage.value = "standard-only";
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
