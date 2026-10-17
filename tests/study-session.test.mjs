import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const context = {};
for (const name of ["answer-history", "study-session"]) {
  vm.runInNewContext(readFileSync(new URL(`../principle_catalog/static/${name}.js`, import.meta.url), "utf8"), context);
}
const history = context.ArchitectAnswerHistory;
const sessions = context.ArchitectStudySession;
const clean = (value) => JSON.parse(JSON.stringify(value));
const DAY = "2026-10-15";
const item = (number, overrides = {}) => ({ itemId: `steel.item-${number}`, revision: "rev1", tier: 1,
  order: number, group: `group-${number % 3}`, section: `section-${number % 4}`, ...overrides });
const items = Array.from({ length: 20 }, (_, index) => item(index + 1));
let serial = 0;
function event(item, { day = "2026-10-14", type = "answer", correct = false, independent = true, ...overrides } = {}) {
  const id = `event-${++serial}`;
  return { version: 1, type, id, itemId: item.itemId, revision: item.revision,
    at: `${day}T10:00:00.000Z`, day, offsetMinutes: 0, sessionId: "test-session",
    ...(type === "answer" ? { attemptId: `attempt-${id}`, choice: correct ? "A" : "B", correctChoice: "A", correct, independent } : {}),
    ...overrides };
}
const select = (overrides = {}) => sessions.selectItems({ items, events: [], tier: 1, day: DAY, ...overrides });
const create = (overrides = {}) => sessions.createSession({ items: select(), tier: 1, now: new Date("2026-10-15T10:00:00.000Z"), ...overrides });

class MemoryStorage {
  values = new Map();
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

test("new sets use ten existing introduction-order items and cumulative tier scope", () => {
  const mixedItems = [item(3, { tier: 3 }), item(2, { tier: 2 }), item(1)];
  assert.deepEqual(clean(select({ items: mixedItems })).map((value) => value.itemId), ["steel.item-1"]);
  assert.deepEqual(clean(select({ items: mixedItems, tier: 2 })).map((value) => value.itemId), ["steel.item-1", "steel.item-2"]);
  assert.equal(select({ tier: 3 }).length, 10);
  assert.equal(select().every((value) => value.kind === "new"), true);
});

test("missing introduction order and tied order have a stable input-order fallback", () => {
  const unordered = [item(9, { order: undefined }), item(8, { order: undefined }), item(7, { order: undefined })];
  assert.deepEqual(clean(select({ items: unordered })).map((value) => value.itemId), unordered.map((value) => value.itemId));
  assert.deepEqual(clean(select({ items: unordered.map((value) => ({ ...value, order: 1 })) })).map((value) => value.itemId), unordered.map((value) => value.itemId));
});

test("mixed sets prioritize consecutive errors, cap review at five, then fill from unanswered", () => {
  const events = items.slice(0, 7).map((value) => event(value));
  events.push(event(items[6], { day: "2026-10-13" }));
  const selected = select({ events });
  assert.equal(selected.length, 10);
  assert.equal(selected[0].itemId, items[6].itemId);
  assert.equal(selected.filter((value) => value.kind === "review").length, 5);
  assert.deepEqual(clean(selected.slice(5)).map((value) => value.itemId), items.slice(7, 12).map((value) => value.itemId));
});

test("review-only sets contain at most ten eligible reviews and never new items", () => {
  const events = items.slice(0, 15).map((value) => event(value));
  const selected = select({ events, mode: "review" });
  assert.equal(selected.length, 10);
  assert.equal(selected.every((value) => value.kind === "review"), true);
  assert.equal(select({ mode: "review" }).length, 0);
});

test("same-day answer and disclosure exclude both review and new items", () => {
  const events = [event(items[0]), event(items[0], { day: DAY, type: "view" }),
    event(items[1], { day: DAY, type: "view" }), event(items[2], { day: DAY })];
  const selected = select({ events });
  assert.equal(selected.some((value) => items.slice(0, 3).some((item) => item.itemId === value.itemId)), false);
  const tomorrow = select({ events, day: "2026-10-16" });
  assert.equal(tomorrow.some((value) => value.itemId === items[0].itemId && value.kind === "review"), true);
  assert.equal(tomorrow.some((value) => value.itemId === items[1].itemId && value.kind === "new"), true);
});

test("sets may be shorter than ten and never refill the sixth review into a mixed set", () => {
  const short = items.slice(0, 7);
  const events = short.map((value) => event(value));
  assert.equal(select({ items: short, events }).length, 5);
  assert.equal(select({ items: short.slice(0, 2) }).length, 2);
  assert.equal(select({ items: [] }).length, 0);
});

test("revision changes reintroduce only the changed question without mutating old history", () => {
  const old = event(items[0], { day: DAY });
  const original = JSON.stringify(old);
  const selected = select({ items: [{ ...items[0], revision: "rev2" }, items[1]], events: [old] });
  assert.equal(selected[0].revision, "rev2");
  assert.equal(selected[0].kind, "new");
  assert.equal(JSON.stringify(old), original);
});

test("assisted mistakes alone do not enter the independent review queue", () => {
  const events = [event(items[0], { type: "view" }), event(items[0], { independent: false })];
  assert.equal(select({ events }).some((value) => value.itemId === items[0].itemId), false);
  assert.equal(sessions.summarizeProgress({ items, events, day: DAY }).review, 0);
});

test("two correct later independent days resolve review according to existing history rules", () => {
  const events = [event(items[0], { day: "2026-10-11" }), event(items[0], { day: "2026-10-12", correct: true }),
    event(items[0], { day: "2026-10-13", correct: true })];
  assert.equal(select({ events, mode: "review" }).length, 0);
});

test("saved sets retain item order, completion, and position across days and catalog reordering", () => {
  const storage = new MemoryStorage();
  const store = sessions.createStore({ storage });
  let state = create();
  state = sessions.markDone(state, items[0].itemId);
  state = sessions.setIndex(state, 3);
  store.write(state);
  const resumed = sessions.reconcileSession(store.read(), [...items].reverse());
  assert.deepEqual(clean(resumed), clean(state));
  assert.deepEqual(clean(sessions.createStore({ storage }).read()), clean(state));
  assert.notDeepEqual(clean(select({ day: "2026-10-16", events: [event(items[0], { day: DAY })] })), clean(state.items));
});

test("reconciliation clears completion only for revised or deleted items and resets to a pending item", () => {
  let state = create({ items: select({ items: items.slice(0, 3) }) });
  state = sessions.markDone(state, items[0].itemId);
  state = sessions.markDone(state, items[1].itemId);
  state = sessions.setIndex(state, 2);
  const latest = [{ ...items[0], revision: "rev2" }, items[1]];
  const updated = sessions.reconcileSession(state, latest);
  assert.equal(updated.items.length, 2);
  assert.equal(updated.items[0].revision, "rev2");
  assert.equal(updated.items[0].kind, "new");
  assert.deepEqual(clean(updated.done), [items[1].itemId]);
  assert.equal(updated.index, 0);
  assert.equal(state.items[0].revision, "rev1");
  assert.deepEqual(clean(state.done), [items[0].itemId, items[1].itemId]);
});

test("reconciliation removes cards moved above the selected tier without adding fresh replacements", () => {
  const state = create({ items: select({ items: items.slice(0, 2) }) });
  const revised = sessions.reconcileSession(state, items.map((value) => ({ ...value, tier: 2 })));
  assert.equal(revised.items.length, 0);
  assert.equal(revised.index, 0);
  assert.deepEqual(clean(revised.done), []);
});

test("marking a card done is idempotent and does not automatically advance", () => {
  const state = create();
  const done = sessions.markDone(sessions.markDone(state, items[0].itemId), items[0].itemId);
  assert.equal(done.done.length, 1);
  assert.equal(done.index, 0);
  assert.equal(state.done.length, 0);
});

test("terminal index is retained even with skipped items until a revised question requires rechecking", () => {
  const state = create({ items: select({ items: items.slice(0, 2) }) });
  const finished = sessions.setIndex(sessions.markDone(state, items[0].itemId), state.items.length);
  assert.equal(finished.index, 2);
  assert.equal(finished.done.length, 1);
  assert.equal(sessions.reconcileSession(finished, items).index, 2);
  const changed = sessions.reconcileSession(finished, items.map((value, index) => index === 0 ? { ...value, revision: "rev2" } : value));
  assert.equal(changed.index, 0);
  assert.equal(changed.done.length, 0);
});

test("strict saved-state validation rejects extra keys, duplicates, invalid dates and out-of-range positions", () => {
  const state = create();
  for (const bad of [{ ...state, extra: true }, { ...state, version: 2 }, { ...state, tier: 0 },
    { ...state, mode: "unknown" }, { ...state, createdAt: "not-a-date" }, { ...state, day: "2026-02-30" },
    { ...state, index: 11 }, { ...state, index: -1 }, { ...state, done: ["not-in-set"] },
    { ...state, done: [items[0].itemId, items[0].itemId] },
    { ...state, items: [state.items[0], state.items[0]] },
    { ...state, items: [{ ...state.items[0], extra: true }] }]) {
    assert.throws(() => sessions.validateSession(bad));
  }
  assert.throws(() => sessions.markDone(state, "not-in-set"));
});

test("corrupt stored data is reported and never silently reset or overwritten", () => {
  const storage = new MemoryStorage();
  storage.setItem(sessions.STORAGE_KEY, "{broken");
  const store = sessions.createStore({ storage });
  assert.throws(() => store.read(), /データは消去していません/);
  assert.throws(() => store.write(create()), /データは消去していません/);
  assert.equal(storage.getItem(sessions.STORAGE_KEY), "{broken");
});

test("storage failures report unsaved changes and preserve the last set", () => {
  const storage = new MemoryStorage();
  const store = sessions.createStore({ storage });
  const state = store.write(create());
  storage.setItem = () => { throw new Error("quota"); };
  assert.throws(() => store.write(sessions.setIndex(state, 2)), /未保存/);
  assert.deepEqual(clean(store.read()), clean(state));
  storage.getItem = () => { throw new Error("blocked"); };
  assert.throws(() => store.read(), /読み取れません/);
});

test("only an explicit clear removes the session and never touches answer events", () => {
  const storage = new MemoryStorage();
  const store = sessions.createStore({ storage });
  store.write(create());
  storage.setItem(`${history.PREFIX}keep`, "answer-data");
  store.clear();
  assert.equal(store.read(), null);
  assert.equal(storage.getItem(`${history.PREFIX}keep`), "answer-data");
});

test("personal counts exclude variants and retired cards, count each main question once today", () => {
  const values = [item(1), item(2, { tier: 2 }), item(3, { tier: 3 })];
  const events = [event(values[0], { day: "2026-10-13" }), event(values[0]),
    event(values[1], { day: DAY, correct: true }), event(values[1], { day: DAY, correct: true, independent: false }),
    event({ ...values[2], revision: "old" }, { day: DAY, correct: true }),
    event({ ...values[0], itemId: "variant.steel.item-1" }, { day: DAY }),
    event(item(99), { day: DAY })];
  const result = sessions.summarizeProgress({ items: values, events, day: DAY });
  assert.deepEqual(clean({ ...result, byTier: undefined, bySection: undefined }),
    { total: 3, unanswered: 1, review: 1, priority: 1, todayAnswered: 2, todayReview: 1 });
  assert.equal(result.byTier[1].priority, 1);
  assert.equal(result.byTier[2].todayAnswered, 1);
  assert.equal(result.byTier[3].unanswered, 1);
  assert.equal(result.bySection[values[0].section].group, values[0].group);
  assert.equal(result.bySection[values[0].section].total, 1);
  const exposed = sessions.summarizeProgress({ items: values, events: [...events, event(values[0], { type: "view", day: DAY })], day: DAY });
  assert.equal(exposed.review, 1);
  assert.equal(exposed.todayReview, 0);
  assert.equal(exposed.todayAnswered, 2);
});

test("invalid input history is not silently ignored and duplicate catalog ids are rejected", () => {
  assert.throws(() => select({ events: [{}] }), /回答履歴/);
  assert.throws(() => select({ items: [items[0], items[0]] }), /識別子/);
  assert.throws(() => select({ tier: "1" }), /範囲/);
  assert.throws(() => select({ day: "2026-02-30" }), /学習日/);
});

test("module also exposes the same API through CommonJS", () => {
  const common = { module: { exports: {} } };
  vm.runInNewContext(readFileSync(new URL("../principle_catalog/static/study-session.js", import.meta.url), "utf8"), common);
  assert.equal(common.module.exports, common.ArchitectStudySession);
  assert.equal(typeof common.module.exports.selectItems, "function");
});
