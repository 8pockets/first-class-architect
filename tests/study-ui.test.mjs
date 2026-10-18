import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const scripts = Object.fromEntries(["answer-history", "study-session", "catalog", "study-ui", "practice-ui"]
  .map((name) => [name, readFileSync(new URL(`../principle_catalog/static/${name}.js`, import.meta.url), "utf8")]));
const camel = (name) => name.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
class Element extends EventTarget {
  constructor(tag = "div", { id = "", dataset = {}, className = "", value = "", text = "" } = {}) {
    super();
    Object.assign(this, { tag, id, dataset, value, textContent: text, hidden: false, disabled: false, children: [], parent: null });
    this.attributes = new Map(); this.classes = new Set(className.split(/\s+/).filter(Boolean)); this._open = false;
    this.classList = { toggle: (name, force) => {
      const on = force ?? !this.classes.has(name);
      if (on) this.classes.add(name); else this.classes.delete(name);
      return on;
    } };
  }
  set className(value) { this.classes = new Set(value.split(/\s+/).filter(Boolean)); }
  get className() { return [...this.classes].join(" "); }
  get open() { return this._open; }
  set open(value) {
    const changed = this._open !== Boolean(value); this._open = Boolean(value);
    if (changed) this.dispatchEvent(new Event("toggle"));
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  get parentNode() { return this.parent; }
  remove() {
    if (!this.parent) return;
    this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null;
  }
  append(...nodes) { nodes.forEach((node) => { node.remove(); node.parent = this; this.children.push(node); }); }
  prepend(...nodes) {
    nodes.forEach((node) => node.remove());
    nodes.forEach((node) => { node.parent = this; });
    this.children.unshift(...nodes);
  }
  replaceChildren(...nodes) { this.children.forEach((node) => { node.parent = null; }); this.children = []; this.append(...nodes); }
  before(node) { node.remove(); const index = this.parent.children.indexOf(this); node.parent = this.parent; this.parent.children.splice(index, 0, node); }
  after(node) { node.remove(); const index = this.parent.children.indexOf(this); node.parent = this.parent; this.parent.children.splice(index + 1, 0, node); }
  replaceWith(node) { node.remove(); const index = this.parent.children.indexOf(this); node.parent = this.parent; this.parent.children.splice(index, 1, node); this.parent = null; }
  descendants() { return this.children.flatMap((child) => [child, ...child.descendants()]); }
  matches(selector) {
    if (selector.endsWith(":not([hidden])")) return !this.hidden && this.matches(selector.slice(0, -":not([hidden])".length));
    if (selector.startsWith("#")) return this.id === selector.slice(1);
    if (selector.startsWith(".")) return this.classes.has(selector.slice(1));
    const match = selector.match(/^([a-z-]+)?\[([^=\]]+)(?:="([^"]*)")?\]$/);
    if (match) {
      const [, tag, attribute, value] = match;
      if (tag && this.tag !== tag) return false;
      const actual = attribute.startsWith("data-") ? this.dataset[camel(attribute.slice(5))] : this.getAttribute(attribute);
      return value === undefined ? actual !== null && actual !== undefined : actual === value;
    }
    return this.tag === selector;
  }
  querySelectorAll(selector) { return this.descendants().filter((node) => node.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
  closest(selector) { return this.matches(selector) ? this : this.parent?.closest(selector) ?? null; }
  focus() { this.focused = true; this.focusCalls = (this.focusCalls || 0) + 1; }
  scrollIntoView() { this.scrolled = true; this.scrollCalls = (this.scrollCalls || 0) + 1; }
  click() {
    if (this.disabled) return;
    const event = new Event("click", { cancelable: true });
    this.dispatchEvent(event);
    if (!event.defaultPrevented && this.tag === "summary" && this.parent.tag === "details") this.parent.open = !this.parent.open;
  }
}
class Storage {
  values = new Map();
  get length() { return this.values.size; }
  key(index) { return [...this.values.keys()][index] ?? null; }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}
let bootSerial = 0;
function boot({ count = 12, storage = new Storage(), beforeUI, revision = "rev1", withPractice = false } = {}) {
  const document = new EventTarget();
  document.body = new Element("body");
  document.createElement = (tag) => new Element(tag);
  document.createComment = (text) => new Element("#comment", { text });
  document.querySelectorAll = (selector) => document.body.querySelectorAll(selector);
  document.querySelector = (selector) => document.body.querySelector(selector);
  document.getElementById = (id) => document.body.descendants().find((node) => node.id === id) ?? null;
  const add = (tag, options, parent = document.body) => { const node = new Element(tag, options); parent.append(node); return node; };
  const ids = ["study-dashboard", "study-tier", "study-status", "study-session", "study-session-title", "study-session-progress",
    "study-session-result", "study-resume", "catalog-controls", "study-return", "study-finish", "study-toggle-answers", "study-metrics",
    "study-map-content", "study-start", "study-review", "study-pause", "study-browse", "catalog-search", "progress-filter",
    "source-kind-filter", "coverage-filter", "review-filter", "history-status", "history-export", "history-import",
    "toggle-visible-answers", "reset-filters", "visible-count", "empty-state", "catalog-browser", "study-session-menu"];
  for (const id of ids) add(["catalog-browser", "study-session-menu"].includes(id) ? "details" : "div",
    { id, value: id === "study-tier" ? "1" : id.endsWith("-filter") ? "all" : "" });
  const $ = (id) => document.getElementById(id);
  add("summary", {}, $("study-session-menu"));
  $("study-resume").hidden = true; $("study-return").hidden = true; $("study-session").hidden = true;
  const nav = add("nav"); nav.setAttribute("aria-label", "分野から探す");
  const root = add("div", { dataset: { catalogRoot: "" } });
  add("div", { id: "study-card-list" }, root);
  const group = add("section", { id: "group-frame", dataset: { catalogGroup: "" } }, root);
  const section = add("section", { id: "subtopic-frame", dataset: { catalogSection: "" } }, group);
  const cards = [];
  for (let i = 0; i < count; i += 1) {
    const card = add("article", { id: `steel.item-${i}`, className: "principle-card", dataset: {
      studyId: `steel.item-${i}`, questionRevision: revision, correctChoice: "A", coverageTier: "1",
      introductionOrder: String(i + 1), group: "frame", section: "frame", groupTitle: "架構", sectionTitle: "骨組",
      type: "principle", progress: "unstarted", sourceKind: "pdf", search: `question-${i}`,
    } }, section);
    add("span", { dataset: { printPosition: "" } }, card);
    for (const choice of ["A", "B"]) {
      const button = add("button", { dataset: { answerChoice: choice } }, card);
      button.setAttribute("aria-controls", `answer-${i}`);
    }
    const disclosure = add("details", { id: `answer-${i}`, dataset: { answerDisclosure: "" } }, card);
    add("summary", {}, disclosure);
    add("p", { dataset: { answerResult: "" } }, card);
    add("button", { dataset: { answerRetry: "" } }, card);
    const log = add("details", { dataset: { answerHistory: "" } }, card);
    add("summary", {}, log); add("ul", { dataset: { answerHistoryList: "" } }, log);
    cards.push(card);
  }
  const prerequisite = add("a", { dataset: { prerequisiteLink: "steel.item-1" } }, cards[0]);
  let practice;
  if (withPractice) {
    practice = add("details", { dataset: { practicePanel: "", practiceId: "practice.steel.item-0", practiceRevision: "practice-rev1", correctChoice: "A" } }, cards[0]);
    const body = add("div", { className: "practice-body" }, practice);
    for (const choice of ["A", "B"]) add("button", { dataset: { practiceChoice: choice } }, body);
    const answer = add("details", { dataset: { practiceAnswer: "" } }, body);
    add("summary", {}, answer);
    add("p", { dataset: { practiceResult: "" } }, body);
  }
  const window = new EventTarget();
  window.localStorage = storage; window.location = { hash: "" }; window.history = { replaceState() {} };
  let now = new Date(2026, 9, 15, 12);
  class Clock extends Date { constructor(...args) { super(...(args.length ? args : [now.getTime()])); } }
  class DetailEvent extends Event { constructor(name, { detail }) { super(name); this.detail = detail; } }
  const serial = ++bootSerial; let uuid = 0;
  const context = { document, window, Event, CustomEvent: DetailEvent, Date: Clock,
    crypto: { randomUUID: () => `boot-${serial}-${++uuid}` } };
  vm.createContext(context);
  vm.runInContext(scripts["answer-history"], context);
  vm.runInContext(scripts["study-session"], context);
  const history = context.ArchitectAnswerHistory;
  const engine = context.ArchitectStudySession;
  const store = history.createStore({ storage, uuid: () => `fixture-${serial}-${++uuid}`, sessionId: `fixture-${serial}`, now: () => now });
  const app = { $, cards, prerequisite, practice, context, history, engine, storage, window, document,
    day: (day) => { now = new Date(2026, 9, day, 12); },
    answer: (index, choice = "A") => cards[index].querySelector(`[data-answer-choice="${choice}"]`).click(),
    fixtureAnswer: (index, choice = "B") => store.answer({ itemId: cards[index].dataset.studyId, revision,
      choice, correctChoice: "A", attemptId: `fixture-attempt-${serial}-${++uuid}` }),
    fixtureView: (index) => store.view(cards[index].dataset.studyId, revision),
    events: () => store.read(), state: () => engine.createStore({ storage }).read(),
    shown: () => document.querySelectorAll(".principle-card:not([hidden])").map((card) => card.dataset.studyId),
  };
  beforeUI?.(app);
  vm.runInContext(scripts.catalog, context);
  vm.runInContext(scripts["study-ui"], context);
  if (withPractice) vm.runInContext(scripts["practice-ui"], context);
  return app;
}

test("today's ten questions show the saved set together without moving cards when answering", () => {
  const app = boot();
  app.$("study-start").click();
  assert.equal(app.state().items.length, 10);
  const selected = Array.from(app.state().items, (item) => item.itemId);
  assert.deepEqual(app.shown(), selected);
  assert.equal(app.cards[0].parent.id, "study-card-list");
  const firstScroll = app.cards[0].scrollCalls;
  const firstFocus = app.cards[0].focusCalls;
  app.answer(0, "B");
  assert.deepEqual(Array.from(app.state().done), ["steel.item-0"]);
  assert.equal(app.state().index, 1);
  assert.deepEqual(app.shown(), selected);
  assert.equal(app.cards[0].scrollCalls, firstScroll);
  assert.equal(app.cards[0].focusCalls, firstFocus);
  assert.equal(app.cards[1].scrollCalls, undefined);
  assert.equal(app.events().filter((event) => event.type === "answer").length, 1);
  app.answer(3, "A");
  assert.equal(app.state().index, 1);
  assert.deepEqual(app.shown(), selected);
  assert.equal(app.$("study-session-progress").textContent, "2 / 10問");
  assert.match(app.$("study-session-progress").getAttribute("aria-label"), /回答 2 \/ 10問 · 残り 8問/);
  assert.equal(app.document.querySelector(".study-card-next"), null);
  assert.match(app.cards[3].querySelector(".study-set-position").textContent, /第4問 · 新規 · 架構/);
});

test("review starts with priority errors and excludes questions disclosed earlier today", () => {
  const app = boot({ beforeUI(app) {
    app.day(13); app.fixtureAnswer(2);
    app.day(14); app.fixtureAnswer(2); app.fixtureAnswer(0); app.fixtureAnswer(1);
    app.day(15); app.fixtureView(0);
  } });
  app.$("study-review").click();
  assert.deepEqual(Array.from(app.state().items, (item) => item.itemId), ["steel.item-2", "steel.item-1"]);
  assert.deepEqual(app.shown(), ["steel.item-2", "steel.item-1"]);
  assert.match(app.cards[2].querySelector(".study-set-position").textContent, /第1問 · 復習/);
  assert.equal(app.state().mode, "review");
  assert.equal(app.state().items.every((item) => item.kind === "review"), true);
});

test("pause and reload resume saved order, done state, and position rather than generating another queue", () => {
  const app = boot();
  app.$("study-start").click(); app.answer(0); app.$("study-pause").click();
  assert.equal(app.$("study-resume").hidden, false);
  assert.equal(app.$("study-session").hidden, true);
  const original = JSON.stringify(app.state());
  const reload = boot({ storage: app.storage });
  reload.$("study-resume").click();
  assert.deepEqual(reload.shown(), Array.from(app.state().items, (item) => item.itemId));
  assert.equal(reload.cards[1].scrolled, true);
  assert.equal(reload.cards[0].scrolled, undefined);
  assert.equal(JSON.stringify(reload.state()), original);
});

test("finishing with skipped questions persists the terminal position and does not show a filter error", () => {
  const app = boot({ count: 2 });
  app.$("study-start").click(); app.answer(0); app.$("study-finish").click();
  assert.equal(app.state().index, 2);
  assert.equal(app.state().done.length, 1);
  assert.equal(app.$("empty-state").hidden, true);
  assert.match(app.$("study-session-result").textContent, /今回の回答 1 \/ 2問/);
  assert.equal(app.$("study-session-progress").textContent, "終了 1/2");
  assert.equal(app.$("study-finish").disabled, true);
  assert.deepEqual(app.shown(), ["steel.item-0", "steel.item-1"]);
  assert.equal(app.cards[0].querySelector("[data-answer-disclosure]").open, true);
  const reload = boot({ count: 2, storage: app.storage });
  assert.equal(reload.$("study-resume").hidden, true);
  reload.$("study-start").click();
  assert.deepEqual(Array.from(reload.state().items, (item) => item.itemId), ["steel.item-1"]);
});

test("a disclosure is not counted as answering and cannot be drawn as a new question on the same day", () => {
  const app = boot({ count: 2 });
  app.cards[0].querySelector("[data-answer-disclosure]").querySelector("summary").click();
  app.$("study-start").click();
  assert.deepEqual(Array.from(app.state().items, (item) => item.itemId), ["steel.item-1"]);
  assert.equal(app.state().done.length, 0);
  assert.equal(app.events().filter((event) => event.type === "answer").length, 0);
});

test("corrupt saved sets disable session controls without deleting the data or blocking catalogue answers", () => {
  const storage = new Storage(); storage.setItem("architect-steel-study-session:v1", "{broken");
  const app = boot({ storage });
  assert.equal(app.$("study-start").disabled, true);
  assert.equal(app.$("study-review").disabled, true);
  assert.match(app.$("study-status").textContent, /削除していません/);
  app.answer(0);
  assert.equal(app.events().filter((event) => event.type === "answer").length, 1);
  assert.equal(storage.getItem(app.engine.STORAGE_KEY), "{broken");
});

test("a session-only save failure allows in-page progress without claiming a saved resume position", () => {
  const app = boot();
  app.$("study-start").click();
  const previous = app.storage.getItem(app.engine.STORAGE_KEY);
  const originalWrite = app.storage.setItem.bind(app.storage);
  app.storage.setItem = (key, value) => {
    if (key === app.engine.STORAGE_KEY) throw new Error("quota");
    originalWrite(key, value);
  };
  app.answer(0);
  assert.deepEqual(app.shown(), Array.from(app.state().items, (item) => item.itemId));
  assert.equal(app.storage.getItem(app.engine.STORAGE_KEY), previous);
  assert.match(app.$("study-status").textContent, /保存できません/);
  app.$("study-pause").click();
  assert.match(app.$("study-resume").textContent, /この画面内/);
  app.$("study-resume").click();
  assert.deepEqual(app.shown(), Array.from(app.state().items, (item) => item.itemId));
  assert.equal(app.cards[1].scrolled, true);
});

test("optional practice has separate events and cannot mark a main question done or clear its review", () => {
  const app = boot({ withPractice: true, beforeUI(app) { app.day(14); app.fixtureAnswer(0); app.day(15); } });
  app.$("study-start").click();
  app.practice.querySelector('[data-practice-choice="A"]').click();
  const answers = app.events().filter((event) => event.type === "answer");
  assert.equal(answers.at(-1).itemId, "practice.steel.item-0");
  assert.equal(answers.at(-1).independent, false);
  assert.equal(app.state().done.length, 0);
  assert.equal(app.history.summarize(app.events(), "steel.item-0", "rev1").review, true);
  const metricCells = app.$("study-metrics").children;
  assert.equal(metricCells[3].children[0].textContent, "0");
});

test("an in-set prerequisite only scrolls within the same page and return keeps answers open", () => {
  const app = boot();
  app.$("study-start").click();
  app.answer(0);
  const selected = app.shown();
  app.prerequisite.click();
  assert.deepEqual(app.shown(), selected);
  assert.equal(app.cards[1].scrolled, true);
  assert.equal(app.$("study-return").hidden, false);
  app.$("study-return").click();
  assert.deepEqual(app.shown(), selected);
  assert.equal(app.$("study-session").hidden, false);
  assert.equal(app.state().index, 1);
  assert.equal(app.cards[0].querySelector("[data-answer-disclosure]").open, true);
});

test("a new question revision reconciles the saved set without reusing old completion", () => {
  const app = boot({ count: 2 });
  app.$("study-start").click(); app.answer(0);
  const reload = boot({ count: 2, storage: app.storage, revision: "rev2" });
  assert.equal(reload.state().done.length, 0);
  assert.equal(reload.state().index, 0);
  assert.equal(reload.state().items[0].revision, "rev2");
  assert.equal(reload.events().filter((event) => event.type === "answer").length, 1);
  assert.match(reload.$("study-status").textContent, /過去の回答は保持/);
});

test("next-day review in the same tab records a fresh independent answer", () => {
  const app = boot({ count: 2 });
  app.$("study-start").click(); app.answer(0, "B"); app.$("study-pause").click();
  app.day(16); app.$("study-review").click();
  assert.deepEqual(app.shown(), ["steel.item-0"]);
  app.answer(0, "A");
  const answers = app.events().filter((event) => event.type === "answer");
  assert.equal(answers.length, 2);
  assert.equal(answers[1].day, "2026-10-16");
  assert.equal(answers[1].independent, true);
  assert.equal(app.state().done.length, 1);
});

test("answering a selected prerequisite during a detour counts as answered in the saved set", () => {
  const app = boot({ count: 2 });
  app.$("study-start").click(); app.prerequisite.click(); app.answer(1);
  app.$("study-return").click();
  assert.deepEqual(Array.from(app.state().done), ["steel.item-1"]);
  app.answer(0);
  assert.match(app.$("study-session-result").textContent, /今回の回答 2 \/ 2問/);
});

test("answering every question automatically finishes without hiding, moving, or refocusing cards", () => {
  const app = boot({ count: 2 });
  app.$("study-start").click();
  const firstScroll = app.cards[0].scrollCalls;
  const firstFocus = app.cards[0].focusCalls;
  app.answer(0, "B");
  const firstAnswer = JSON.stringify(app.events().find((event) => event.type === "answer"));
  assert.equal(app.state().index, 1);
  app.answer(1, "A");
  assert.equal(app.state().index, 2);
  assert.equal(app.state().done.length, 2);
  assert.equal(app.$("study-finish").disabled, true);
  assert.equal(app.$("study-session-result").hidden, false);
  assert.deepEqual(app.shown(), ["steel.item-0", "steel.item-1"]);
  assert.equal(app.cards[0].scrollCalls, firstScroll);
  assert.equal(app.cards[0].focusCalls, firstFocus);
  assert.equal(app.cards[1].scrollCalls, undefined);
  assert.equal(app.cards[1].focusCalls, undefined);
  assert.equal(app.$("study-session").scrollCalls, undefined);
  assert.equal(app.cards.every((card) => card.querySelector("[data-answer-disclosure]").open), true);
  assert.equal(JSON.stringify(app.events().find((event) => event.type === "answer")), firstAnswer);
  assert.equal(app.events().filter((event) => event.type === "answer").length, 2);
  app.$("study-pause").click();
  assert.equal(app.$("study-resume").hidden, true);
});

test("legacy saved positions resume the same set at its first unanswered question", () => {
  const app = boot({ count: 3 });
  app.$("study-start").click(); app.answer(1);
  const store = app.engine.createStore({ storage: app.storage });
  store.write(app.engine.setIndex(app.state(), 2));
  const reload = boot({ count: 3, storage: app.storage });
  assert.equal(reload.state().index, 0);
  assert.deepEqual(Array.from(reload.state().done), ["steel.item-1"]);
  reload.$("study-resume").click();
  assert.deepEqual(reload.shown(), ["steel.item-0", "steel.item-1", "steel.item-2"]);
  assert.equal(reload.cards[0].scrolled, true);
});

test("an out-of-set prerequisite is appended as a supplement without closing answers or counting toward the set", () => {
  const app = boot();
  app.prerequisite.dataset.prerequisiteLink = "steel.item-11";
  app.$("study-start").click(); app.answer(0);
  const selected = app.shown();
  app.prerequisite.click();
  assert.deepEqual(app.shown(), [...selected, "steel.item-11"]);
  assert.equal(app.cards[0].querySelector("[data-answer-disclosure]").open, true);
  assert.match(app.cards[11].querySelector(".study-set-position").textContent, /集計対象外/);
  assert.equal(app.cards[11].matches(".study-set-supplement"), true);
  app.answer(11);
  assert.equal(app.state().done.length, 1);
  assert.equal(app.state().items.length, 10);
  app.$("study-return").click();
  assert.deepEqual(app.shown(), [...selected, "steel.item-11"]);
  assert.equal(app.cards[11].querySelector("[data-answer-disclosure]").open, true);
  app.$("study-pause").click();
  assert.equal(app.document.querySelectorAll(".study-set-position").length, 0);
  assert.equal(app.document.querySelectorAll(".study-set-supplement").length, 0);
  assert.equal(app.$("study-card-list").children.length, 0);
  assert.equal(app.cards.every((card) => card.parent.id === "subtopic-frame"), true);
  assert.equal(app.document.querySelectorAll(".principle-card").length, 12);
  assert.deepEqual(app.shown(), app.cards.map((card) => card.dataset.studyId));
});

test("the set bulk toggle opens only the displayed questions and does not count views as answers", () => {
  const app = boot();
  app.$("study-start").click();
  app.$("study-toggle-answers").click();
  assert.equal(app.cards.slice(0, 10).every((card) => card.querySelector("[data-answer-disclosure]").open), true);
  assert.equal(app.cards.slice(10).some((card) => card.querySelector("[data-answer-disclosure]").open), false);
  assert.equal(app.state().done.length, 0);
  assert.equal(app.events().filter((event) => event.type === "answer").length, 0);
  app.$("study-toggle-answers").click();
  assert.equal(app.cards.every((card) => !card.querySelector("[data-answer-disclosure]").open), true);
});

test("returning to the catalogue restores its original filter, card locations, and ordering", () => {
  const app = boot();
  app.$("catalog-search").value = "question-11";
  app.$("catalog-search").dispatchEvent(new Event("input"));
  assert.deepEqual(app.shown(), ["steel.item-11"]);
  app.$("study-start").click();
  assert.equal(app.shown().length, 10);
  app.$("study-pause").click();
  assert.deepEqual(app.shown(), ["steel.item-11"]);
  assert.equal(app.cards.every((card) => card.parent.id === "subtopic-frame"), true);
  assert.equal(app.cards[0].parent.hidden, false);
  assert.equal(app.cards[0].parent.parent.hidden, false);
  assert.equal(app.$("study-card-list").hidden, true);
  assert.equal(app.document.querySelectorAll(".study-set-position").length, 0);
  app.$("reset-filters").click();
  assert.deepEqual(app.shown(), app.cards.map((card) => card.dataset.studyId));
});

test("answers after explicit finish update history without reopening the finished set", () => {
  const app = boot({ count: 3 });
  app.$("study-start").click(); app.answer(0); app.$("study-finish").click();
  app.answer(1);
  assert.equal(app.state().index, 3);
  assert.equal(app.state().done.length, 2);
  assert.match(app.$("study-session-result").textContent, /今回の回答 2 \/ 3問/);
  assert.deepEqual(app.shown(), ["steel.item-0", "steel.item-1", "steel.item-2"]);
  app.$("study-pause").click();
  assert.equal(app.$("study-resume").hidden, true);
});
