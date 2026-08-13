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

  focus() {}
}

const bootCatalog = () => {
  const disclosures = [new FakeElement(), new FakeElement(), new FakeElement()];
  disclosures.forEach((disclosure) => {
    disclosure.open = true;
  });
  const cards = [
    new FakeElement({
      dataset: { search: "解説だけの語", type: "principle", progress: "unstarted" },
    }),
  ];
  const sections = [
    {
      hidden: false,
      querySelector: () => cards.find((card) => !card.hidden) ?? null,
    },
  ];
  const root = {
    querySelectorAll: (selector) => {
      if (selector === ".principle-card") return cards;
      if (selector === "[data-catalog-section]") return sections;
      if (selector === "[data-disclosure]") return disclosures;
      return [];
    },
  };
  const search = new FakeElement();
  const progress = new FakeElement({ value: "all" });
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
    ["#reset-filters", reset],
    ["#visible-count", visibleCount],
    ["#empty-state", empty],
  ]);
  const document = {
    querySelector: (selector) => elements.get(selector) ?? null,
    querySelectorAll: (selector) =>
      selector === "[data-filter-type]" ? typeButtons : [],
  };
  const window = new EventTarget();

  vm.runInNewContext(script, { document, Event, window });

  return { cards, disclosures, progress, reset, search, typeButtons, window };
};

const open = (disclosure) => {
  disclosure.open = true;
  disclosure.dispatchEvent(new Event("toggle"));
};

test("answers start closed and opening one closes the previous answer", () => {
  const { disclosures } = bootCatalog();

  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);
  open(disclosures[0]);
  open(disclosures[1]);

  assert.deepEqual(disclosures.map(({ open }) => open), [false, true, false]);
});

test("changing any search or filter control closes the open answer", () => {
  const { disclosures, progress, reset, search, typeButtons } = bootCatalog();
  const controls = [
    [search, "input"],
    [progress, "change"],
    [typeButtons[1], "click"],
    [reset, "click"],
  ];

  for (const [control, eventName] of controls) {
    open(disclosures[0]);
    control.dispatchEvent(new Event(eventName));
    assert.equal(disclosures[0].open, false, `${eventName} must close the answer`);
  }
});

test("search finds hidden explanation text without opening the answer", () => {
  const { cards, disclosures, search } = bootCatalog();
  open(disclosures[0]);
  search.value = "解説だけの語";

  search.dispatchEvent(new Event("input"));

  assert.equal(disclosures[0].open, false);
  assert.equal(cards[0].hidden, false);
});

test("restoring the page from browser history closes every answer", () => {
  const { disclosures, window } = bootCatalog();
  open(disclosures[2]);

  window.dispatchEvent(new Event("pageshow"));

  assert.deepEqual(disclosures.map(({ open }) => open), [false, false, false]);
});
