import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const context = {};
vm.runInNewContext(readFileSync(new URL("../principle_catalog/static/answer-history.js", import.meta.url), "utf8"), context);
const history = context.ArchitectAnswerHistory;
const clean = (value) => JSON.parse(JSON.stringify(value));

export class MemoryStorage {
  values = new Map();
  get length() { return this.values.size; }
  key(index) { return [...this.values.keys()][index] ?? null; }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
}

function boot({ storage = new MemoryStorage(), sessionId = "session1" } = {}) {
  let count = 0;
  let date = new Date(2026, 9, 6, 12);
  const store = history.createStore({ storage, sessionId, now: () => date,
    uuid: () => `${sessionId}-event-${++count}` });
  return { store, storage, day: (day) => { date = new Date(2026, 9, day, 12); },
    at: (value) => { date = value; },
    answer: (choice, attemptId = `${sessionId}-attempt-${++count}`, revision = "rev1") =>
      store.answer({ itemId: "structure.steel.test", revision, attemptId, choice, correctChoice: "A" }),
    summary: (revision = "rev1") => history.summarize(store.read(), "structure.steel.test", revision),
  };
}

test("first choice is immutable for its attempt and repeated clicks do not count", () => {
  const app = boot();
  const first = app.answer("B", "attempt1");
  const second = app.answer("A", "attempt1");
  assert.equal(first.id, second.id);
  assert.equal(second.choice, "B");
  assert.equal(app.summary().answers.length, 1);
  assert.equal(app.summary().review, true);
});

test("viewing answers does not record an answer and later choices are assisted", () => {
  const app = boot();
  app.store.view("structure.steel.test", "rev1");
  assert.equal(app.summary().answers.length, 0);
  assert.equal(app.summary().unanswered, true);
  assert.equal(app.answer("B").independent, false);
  assert.equal(app.summary().review, false);
  assert.equal(app.summary().wrongStreak, 0);
});

test("retry, page reload, and another tab cannot turn today's disclosure into independent success", () => {
  const app = boot();
  app.answer("B");
  assert.equal(app.answer("A").independent, false);
  const reload = boot({ storage: app.storage, sessionId: "session2" });
  assert.equal(reload.answer("A").independent, false);
  assert.equal(reload.summary().review, true);
  assert.equal(reload.summary().wrongStreak, 1);
  assert.equal(reload.summary().recoveryDays, 0);
});

test("two independent wrong attempts make priority; two later distinct local days clear it", () => {
  const app = boot();
  app.answer("B");
  app.day(7); app.answer("B");
  assert.equal(app.summary().priority, true);
  assert.equal(app.summary().wrongStreak, 2);
  app.day(8); app.answer("A");
  assert.equal(app.summary().priority, false);
  assert.equal(app.summary().review, true);
  assert.equal(app.summary().recoveryDays, 1);
  app.answer("A");
  assert.equal(app.summary().review, true);
  app.day(9); app.answer("A");
  assert.equal(app.summary().review, false);
  assert.equal(app.summary().answers.length, 5);
});

test("a new independent error resets the recovery days", () => {
  const app = boot();
  app.answer("B");
  app.day(7); app.answer("A");
  app.day(8); app.answer("B");
  assert.equal(app.summary().recoveryDays, 0);
  app.day(9); app.answer("A");
  assert.equal(app.summary().review, true);
});

test("assisted errors do not add to an independent error streak", () => {
  const app = boot();
  app.answer("B");
  app.answer("B");
  assert.equal(app.summary().wrongStreak, 1);
  assert.equal(app.summary().priority, false);
});

test("a question revision has fresh status without deleting or regrading the past", () => {
  const app = boot();
  app.answer("B");
  const old = app.store.read()[0];
  const fresh = app.summary("rev2");
  assert.equal(fresh.unanswered, true);
  assert.equal(fresh.review, false);
  assert.equal(fresh.oldAnswers.length, 1);
  assert.equal(fresh.hasHistory, true);
  assert.equal(app.answer("A", "new-attempt", "rev2").independent, true);
  assert.deepEqual(clean(app.store.read().find((event) => event.id === old.id)), clean(old));
});

test("two tabs append without overwriting each other's records", () => {
  const first = boot();
  const second = boot({ storage: first.storage, sessionId: "session2" });
  first.answer("B", "tab1-answer");
  second.answer("A", "tab2-answer");
  assert.equal(first.store.read().length, 2);
  assert.equal(second.store.read().length, 2);
  assert.equal(second.summary().independentAnswers.length, 1);
});

test("backup round trips, deduplicates and merges without replacing existing answers", () => {
  const first = boot(); first.answer("B");
  const second = boot({ sessionId: "session2" }); second.answer("A");
  assert.equal(second.store.importBackup(first.store.exportBackup()), 1);
  assert.equal(second.store.importBackup(first.store.exportBackup()), 0);
  assert.equal(second.store.read().length, 2);
  assert.deepEqual(clean(history.parseBackup(second.store.exportBackup())), clean(second.store.read()));
});

test("malformed backups and conflicting duplicate ids cause no writes", () => {
  const app = boot(); app.answer("B");
  const original = app.store.exportBackup();
  const changed = JSON.parse(original);
  changed.events[0].choice = "A"; changed.events[0].correct = true;
  assert.throws(() => app.store.importBackup(JSON.stringify(changed)), /同じ履歴ID/);
  assert.throws(() => app.store.importBackup("{bad"), /JSON/);
  assert.throws(() => app.store.importBackup('{"version":1,"events":[]}'), /バックアップではありません/);
  const invalid = JSON.parse(original); invalid.events[0].correct = true;
  assert.throws(() => app.store.importBackup(JSON.stringify(invalid)), /採点データ/);
  assert.equal(app.store.exportBackup(), original);
});

test("stored corruption fails visibly and is never replaced or deleted", () => {
  const app = boot();
  app.storage.setItem(history.PREFIX + "broken", "{bad");
  assert.throws(() => app.answer("A"), /読み取れません/);
  assert.equal(app.storage.getItem(history.PREFIX + "broken"), "{bad");
  assert.equal(app.storage.length, 1);
});

test("quota failure reports unsaved record and keeps old data", () => {
  const app = boot(); app.answer("B");
  app.storage.setItem = () => { throw new Error("QuotaExceededError"); };
  assert.throws(() => app.answer("A"), /未保存/);
  assert.equal(app.store.read().length, 1);
});

test("local day is retained with its offset, not reconstructed from UTC or another device zone", () => {
  const event = {
    version: 1, type: "answer", id: "e1", itemId: "i1", revision: "r1", sessionId: "s1",
    at: "2026-10-05T15:30:00.000Z", day: "2026-10-06", offsetMinutes: -540,
    attemptId: "a1", choice: "A", correctChoice: "A", correct: true, independent: true,
  };
  assert.equal(history.validateEvent(event).day, "2026-10-06");
  assert.throws(() => history.validateEvent({ ...event, day: "2026-10-05" }), /日時/);
  const app = boot();
  app.at(new Date(2026, 9, 6, 0, 1));
  assert.equal(app.answer("A").day, "2026-10-06");
});

test("simultaneous cross-tab independent flags only count one first exposure per local day", () => {
  const app = boot(); app.answer("B");
  const first = app.store.read()[0];
  const second = { ...first, id: "z-later", at: new Date(Date.parse(first.at) + 1000).toISOString(),
    attemptId: "other", choice: "A", correct: true, independent: true };
  const summary = history.summarize([first, second], first.itemId, first.revision);
  assert.equal(summary.independentAnswers.length, 1);
  assert.equal(summary.review, true);
});

test("a same-millisecond retry with a smaller random id cannot erase the first independent mistake", () => {
  const app = boot(); app.answer("B");
  const first = app.store.read()[0];
  const retry = { ...first, id: "aaa-retry", attemptId: "retry-attempt", choice: "A", correct: true, independent: false };
  const summary = history.summarize([retry, first], first.itemId, first.revision);
  assert.equal(summary.independentAnswers.length, 1);
  assert.equal(summary.review, true);
  assert.equal(summary.latest.id, "aaa-retry");
});

test("a backup cannot add a second answer record for one attempt under another event id", () => {
  const app = boot(); app.answer("B");
  const before = app.store.exportBackup();
  const backup = JSON.parse(before);
  backup.events[0].id = "copied-id";
  assert.throws(() => app.store.importBackup(JSON.stringify(backup)), /同じ回答試行/);
  assert.equal(app.store.exportBackup(), before);
});

test("a partly completed import preserves existing and successfully added entries on quota error", () => {
  const source = boot();
  source.answer("B"); source.day(7); source.answer("A");
  const target = boot({ sessionId: "target" });
  target.answer("B");
  const write = target.storage.setItem.bind(target.storage);
  let writes = 0;
  target.storage.setItem = (key, value) => {
    if (++writes > 1) throw new Error("QuotaExceededError");
    write(key, value);
  };
  assert.throws(() => target.store.importBackup(source.store.exportBackup()), /1件を追加した時点/);
  assert.equal(target.store.read().length, 2);
  assert.equal(target.store.read().some((event) => event.sessionId === "target"), true);
});

test("review filter predicates distinguish unanswered, review, priority and old history", () => {
  const app = boot();
  assert.equal(history.matchesFilter(app.summary(), "unanswered"), true);
  app.answer("B");
  assert.equal(history.matchesFilter(app.summary(), "review"), true);
  assert.equal(history.matchesFilter(app.summary(), "priority"), false);
  assert.equal(history.matchesFilter(app.summary(), "history"), true);
  assert.equal(history.matchesFilter(app.summary("rev2"), "history"), true);
  assert.equal(history.matchesFilter(app.summary("rev2"), "review"), false);
});
