import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const script = readFileSync(
  new URL("../principle_catalog/static/catalog.js", import.meta.url),
  "utf8",
);
const historyScript = readFileSync(
  new URL("../principle_catalog/static/answer-history.js", import.meta.url), "utf8",
);
let bootSerial = 0;

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
    this.elements = new Map();
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
    return this.elements.get(selector) ?? null;
  }

  closest(selector) {
    if (selector === ".principle-card") return this.card ?? null;
    return null;
  }

  focus() {}

  replaceChildren(...children) { this.children = children; }

  scrollIntoView() {
    this.scrolledIntoView = true;
  }
}

const bootCatalog = ({ catalogCards, withHistory = false, storage } = {}) => {
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
  if (withHistory) cards.forEach((card, index) => {
    Object.assign(card.dataset, { studyId: `steel.test-${index}`, questionRevision: "rev1", correctChoice: "A" });
    for (const selector of ["[data-answer-result]", "[data-answer-retry]", "[data-answer-history]", "[data-answer-history-list]", '[data-research-search="explanation"]']) {
      card.elements.set(selector, new FakeElement());
    }
  });
  const disclosures = cards.map(
    (_card, index) => new FakeElement({ id: `answer-${index + 1}` }),
  );
  const answerChoices = cards.flatMap((card, index) =>
    ["A", "B"].map((letter) => {
      const choice = new FakeElement({ dataset: { answerChoice: letter } });
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
  const reviewFilter = new FakeElement({ value: "all" });
  const historyStatus = new FakeElement();
  const historyExport = new FakeElement();
  const historyImport = new FakeElement();
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
  if (withHistory) {
    elements.set("#review-filter", reviewFilter);
    elements.set("#history-status", historyStatus);
    elements.set("#history-export", historyExport);
    elements.set("#history-import", historyImport);
  }
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
    createElement: () => new FakeElement(),
  };
  const window = new EventTarget();
  window.location = { hash: "" };
  window.history = {
    replacement: null,
    replaceState: (_state, _title, replacement) => {
      window.history.replacement = replacement;
    },
  };
  const values = new Map();
  window.localStorage = storage ?? {
    get length() { return values.size; },
    key: (index) => [...values.keys()][index] ?? null,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  const serial = ++bootSerial;
  let id = 0;
  const context = { document, Event, window, crypto: { randomUUID: () => `boot-${serial}-id-${++id}` } };
  vm.createContext(context);
  if (withHistory) vm.runInContext(historyScript, context);
  vm.runInContext(script, context);

  return {
    answerChoices,
    cards,
    disclosures,
    groups,
    canonicalCard,
    coverage,
    reviewFilter,
    historyStatus,
    historyImport,
    historyExport,
    storedEvents: () => {
      const result = [];
      for (let i = 0; i < window.localStorage.length; i += 1) {
        const key = window.localStorage.key(i);
        if (key.startsWith("architect-steel-history:v1:event:")) result.push(JSON.parse(window.localStorage.getItem(key)));
      }
      return result;
    },
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

test("answer history grades the first button only, and native keyboard click is not duplicated", () => {
  const app = bootCatalog({ withHistory: true });
  pressChoice(app.answerChoices[1], "Enter");
  assert.equal(app.storedEvents().length, 0);
  app.answerChoices[1].dispatchEvent(new Event("click"));
  app.answerChoices[0].dispatchEvent(new Event("click"));
  app.answerChoices[1].dispatchEvent(new Event("click"));
  const answers = app.storedEvents().filter((event) => event.type === "answer");
  assert.equal(answers.length, 1);
  assert.equal(answers[0].choice, "B");
  assert.equal(answers[0].correct, false);
  assert.equal(answers[0].independent, true);
  assert.match(app.cards[0].querySelector("[data-answer-result]").textContent, /今回：Bを選択 → 不正解/);
  assert.equal(app.disclosures[0].open, true);
});

test("individual and bulk answer viewing never counts as answering and later answers are assisted", () => {
  const app = bootCatalog({ withHistory: true });
  app.disclosures[0].summary.dispatchEvent(new Event("click"));
  assert.equal(app.storedEvents().filter((event) => event.type === "answer").length, 0);
  app.answerChoices[0].dispatchEvent(new Event("click"));
  app.toggleVisibleAnswers.dispatchEvent(new Event("click"));
  app.answerChoices[2].dispatchEvent(new Event("click"));
  const answers = app.storedEvents().filter((event) => event.type === "answer");
  assert.equal(answers.length, 2);
  assert.equal(answers.every((event) => !event.independent), true);
});

test("explicit retry records a new assisted attempt without erasing the first answer", () => {
  const app = bootCatalog({ withHistory: true });
  app.answerChoices[1].dispatchEvent(new Event("click"));
  assert.equal(app.cards[0].querySelector("[data-answer-retry]").hidden, false);
  app.cards[0].querySelector("[data-answer-retry]").dispatchEvent(new Event("click"));
  assert.equal(app.cards[0].querySelector("[data-answer-retry]").hidden, true);
  assert.equal(app.disclosures[0].open, false);
  app.answerChoices[0].dispatchEvent(new Event("click"));
  const answers = app.storedEvents().filter((event) => event.type === "answer");
  assert.equal(answers.length, 2);
  assert.deepEqual(answers.map((event) => event.choice), ["B", "A"]);
  assert.equal(answers[1].independent, false);
  assert.match(app.cards[0].querySelector("[data-answer-result]").textContent, /要復習/);
});

test("review filters combine with coverage and never hide cards while answering", () => {
  const app = bootCatalog({ withHistory: true });
  app.reviewFilter.value = "unanswered";
  app.reviewFilter.dispatchEvent(new Event("change"));
  app.answerChoices[1].dispatchEvent(new Event("click"));
  assert.equal(app.cards[0].hidden, false, "an answer does not cause a card to jump out of view");
  app.reviewFilter.dispatchEvent(new Event("change"));
  assert.equal(app.cards[0].hidden, true);
  app.reviewFilter.value = "review";
  app.reviewFilter.dispatchEvent(new Event("change"));
  assert.deepEqual(app.cards.map((card) => card.hidden), [false, true, true]);
  app.coverage.value = "standard-only";
  app.coverage.dispatchEvent(new Event("change"));
  assert.deepEqual(app.cards.map((card) => card.hidden), [true, true, true]);
  app.reset.dispatchEvent(new Event("click"));
  assert.equal(app.reviewFilter.value, "all");
  assert.deepEqual(app.cards.map((card) => card.hidden), [false, false, false]);
});

test("reload retains history but does not leak the previous selected letter before opening history", () => {
  const first = bootCatalog({ withHistory: true });
  first.answerChoices[1].dispatchEvent(new Event("click"));
  const app = bootCatalog({ withHistory: true, storage: first.window.localStorage });
  const result = app.cards[0].querySelector("[data-answer-result]").textContent;
  assert.match(result, /要復習/);
  assert.doesNotMatch(result, /Bを選択/);
  assert.match(app.cards[0].querySelector("[data-answer-history-list]").children[0].textContent, /B → 不正解/);
  app.answerChoices[0].dispatchEvent(new Event("click"));
  assert.equal(app.storedEvents().filter((event) => event.type === "answer").at(-1).independent, false);
});

test("opening an empty history panel does not pretend that an answer was revealed", () => {
  const app = bootCatalog({ withHistory: true });
  const panel = app.cards[0].querySelector("[data-answer-history]");
  panel.open = true;
  panel.dispatchEvent(new Event("toggle"));
  app.window.dispatchEvent(new Event("focus"));
  assert.equal(app.storedEvents().length, 0);
  app.answerChoices[0].dispatchEvent(new Event("click"));
  const answers = app.storedEvents().filter((event) => event.type === "answer");
  assert.equal(answers.length, 1);
  assert.equal(answers[0].independent, true);
});

test("storage failure is explicit and never prevents independent answer disclosures", () => {
  const app = bootCatalog({ withHistory: true });
  app.window.localStorage.setItem = () => { throw new Error("QuotaExceededError"); };
  app.answerChoices[0].dispatchEvent(new Event("click"));
  assert.match(app.historyStatus.textContent, /保存できません/);
  assert.equal(app.historyStatus.dataset.error, "true");
  assert.match(app.cards[0].querySelector("[data-answer-result]").textContent, /保存されていません/);
  assert.equal(app.disclosures[0].open, true);
  app.answerChoices[0].dispatchEvent(new Event("click"));
  assert.equal(app.storedEvents().length, 0);
});

test("viewing during a storage failure remains assisted after the answer is closed and storage recovers", () => {
  const app = bootCatalog({ withHistory: true });
  const save = app.window.localStorage.setItem;
  app.window.localStorage.setItem = () => { throw new Error("QuotaExceededError"); };
  openAnswer(app.disclosures[0]);
  app.disclosures[0].open = false;
  app.disclosures[0].dispatchEvent(new Event("toggle"));
  assert.equal(app.storedEvents().length, 0);
  app.window.localStorage.setItem = save;
  app.answerChoices[0].dispatchEvent(new Event("click"));
  const answers = app.storedEvents().filter((event) => event.type === "answer");
  assert.equal(answers.length, 1);
  assert.equal(answers[0].independent, false);
});

test("question-only printing does not mark answers exposed", () => {
  const app = bootCatalog({ withHistory: true });
  app.window.dispatchEvent(new Event("beforeprint"));
  assert.equal(app.storedEvents().length, 0);
  app.answerChoices[0].dispatchEvent(new Event("click"));
  assert.equal(app.storedEvents()[0].independent, true);
});

test("following the external explanation search marks the next answer assisted", () => {
  const app = bootCatalog({ withHistory: true });
  app.cards[0].querySelector('[data-research-search="explanation"]').dispatchEvent(new Event("click"));
  app.cards[1].querySelector('[data-research-search="explanation"]').dispatchEvent(new Event("auxclick"));
  app.answerChoices[0].dispatchEvent(new Event("click"));
  app.answerChoices[2].dispatchEvent(new Event("click"));
  const answers = app.storedEvents().filter((event) => event.type === "answer");
  assert.equal(answers.length, 2);
  assert.equal(answers.every((event) => !event.independent), true);
});

test("answers start closed and opening a lower answer keeps the answer above open", () => {
  const { disclosures } = bootCatalog();

  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);
  openAnswer(disclosures[0]);
  openAnswer(disclosures[1]);

  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, false]);
});

test("opening a lower answer does not move the viewport when an answer above is open", () => {
  const { answerChoices, disclosures, window } = bootCatalog();
  let answerAboveOpen = disclosures[0].open;
  Object.defineProperty(disclosures[0], "open", {
    configurable: true,
    get: () => answerAboveOpen,
    set: (open) => {
      if (answerAboveOpen && !open) window.scrollY -= 325;
      answerAboveOpen = open;
    },
  });
  window.scrollY = 2940;

  answerChoices[0].dispatchEvent(new Event("click"));
  const scrollYBefore = window.scrollY;
  answerChoices[2].dispatchEvent(new Event("click"));

  assert.equal(window.scrollY, scrollYBefore);
  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, false]);
});

test("choosing A or B opens its answer without collapsing another answer", () => {
  const { answerChoices, disclosures } = bootCatalog();

  answerChoices[0].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, false]);
  assert.deepEqual(
    answerChoices.slice(0, 2).map((choice) => choice.getAttribute("aria-expanded")),
    ["true", "true"],
  );

  answerChoices[2].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, false]);
  assert.deepEqual(
    answerChoices.slice(0, 4).map((choice) => choice.getAttribute("aria-expanded")),
    ["true", "true", "true", "true"],
  );

  answerChoices[2].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, false]);
});

test("native Enter and Space rely only on the browser synthesized click", () => {
  const { answerChoices, disclosures } = bootCatalog();

  const enterEvent = pressChoice(answerChoices[0], "Enter");
  assert.equal(enterEvent.defaultPrevented, false);
  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);
  answerChoices[0].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, false]);

  const spaceEvent = pressChoice(answerChoices[2], " ");
  assert.equal(spaceEvent.defaultPrevented, false);
  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, false]);
  answerChoices[2].dispatchEvent(new Event("click"));
  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, false]);
});

test("clicking a closed answer summary does not collapse the current answer", () => {
  const { disclosures } = bootCatalog();
  openAnswer(disclosures[0]);

  disclosures[1].summary.dispatchEvent(new Event("click"));

  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, false]);

  disclosures[1].open = true;
  disclosures[1].dispatchEvent(new Event("toggle"));
  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, false]);
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

test("using an individual answer after bulk open leaves unrelated answers in place", () => {
  const { disclosures, toggleVisibleAnswers } = bootCatalog();
  toggleVisibleAnswers.dispatchEvent(new Event("click"));
  for (const disclosure of disclosures) {
    disclosure.dispatchEvent(new Event("toggle"));
  }
  assert.deepEqual(disclosures.map(({ open }) => open), [true, true, true]);

  disclosures[1].summary.dispatchEvent(new Event("click"));
  disclosures[1].open = false;
  disclosures[1].dispatchEvent(new Event("toggle"));

  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, true]);
  assert.equal(toggleVisibleAnswers.textContent, "表示中の答えをすべて開く");
  assert.equal(toggleVisibleAnswers.attributes.get("aria-pressed"), "false");

  openAnswer(disclosures[2]);
  openAnswer(disclosures[0]);
  assert.deepEqual(disclosures.map(({ open }) => open), [true, false, true]);
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
