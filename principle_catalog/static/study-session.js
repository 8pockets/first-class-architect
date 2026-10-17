/* Small, resumable study sets. Answer history remains the source of truth. */
((scope) => {
  "use strict";

  const STORAGE_KEY = "architect-steel-study-session:v1";
  const MAX_ITEMS = 10;
  const MODES = ["mixed", "review"];
  const validToken = (value) => typeof value === "string" && /^[a-zA-Z0-9._:-]{1,200}$/.test(value);
  const validLabel = (value) => typeof value === "string" && value.length > 0 && value.length <= 200;
  const validTier = (value) => Number.isInteger(value) && value >= 1 && value <= 3;
  const ownKeys = (value, keys) => value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));

  function historyApi() {
    if (!scope.ArchitectAnswerHistory) throw new Error("回答履歴の機能を読み込めないため、学習セットを作成できません。");
    return scope.ArchitectAnswerHistory;
  }

  function checkDay(day) {
    if (typeof day !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(day) ||
        !Number.isFinite(Date.parse(`${day}T00:00:00.000Z`)) ||
        new Date(`${day}T00:00:00.000Z`).toISOString().slice(0, 10) !== day) {
      throw new Error("学習日が不正です。");
    }
    return day;
  }

  function checkSettings(tier, mode) {
    if (!validTier(tier) || !MODES.includes(mode)) throw new Error("学習セットの範囲・種類が不正です。");
  }

  function catalogItems(items) {
    if (!Array.isArray(items)) throw new Error("学習問題の一覧が不正です。");
    const seen = new Set();
    return items.map((item, index) => {
      if (!item || !validToken(item.itemId) || !validToken(item.revision) || !validTier(item.tier) ||
          !validLabel(item.group) || !validLabel(item.section) ||
          (item.order !== undefined && (!Number.isSafeInteger(item.order) || item.order < 0)) || seen.has(item.itemId)) {
        throw new Error("学習問題の識別子・分類・導入順が不正です。");
      }
      seen.add(item.itemId);
      return { ...item, order: item.order ?? index + 1, inputIndex: index };
    });
  }

  function indexedEvents(events) {
    const result = new Map();
    for (const event of historyApi().mergeEvents(events)) {
      if (!result.has(event.itemId)) result.set(event.itemId, []);
      result.get(event.itemId).push(event);
    }
    return result;
  }

  function itemStatus(item, events, day) {
    const related = events.get(item.itemId) ?? [];
    return {
      ...historyApi().summarize(related, item.itemId, item.revision),
      exposedToday: related.some((event) => event.revision === item.revision && event.day === day),
      answeredToday: related.some((event) => event.type === "answer" && event.day === day),
    };
  }

  function selectItems({ items, events, tier = 1, mode = "mixed", day = historyApi().localDay(new Date()) }) {
    checkSettings(tier, mode);
    checkDay(day);
    const history = indexedEvents(events);
    const eligible = catalogItems(items)
      .filter((item) => item.tier <= tier)
      .sort((a, b) => a.order - b.order || a.inputIndex - b.inputIndex)
      .map((item) => ({ item, status: itemStatus(item, history, day) }))
      .filter(({ status }) => !status.exposedToday);
    const reviews = eligible.filter(({ status }) => status.review)
      .sort((a, b) => Number(b.status.priority) - Number(a.status.priority))
      .slice(0, mode === "review" ? MAX_ITEMS : 5)
      .map(({ item }) => ({ itemId: item.itemId, revision: item.revision, kind: "review" }));
    if (mode === "review") return reviews;
    const fresh = eligible.filter(({ status }) => status.unanswered)
      .slice(0, MAX_ITEMS - reviews.length)
      .map(({ item }) => ({ itemId: item.itemId, revision: item.revision, kind: "new" }));
    return [...reviews, ...fresh];
  }

  function validateSelection(items) {
    if (!Array.isArray(items) || items.length > MAX_ITEMS) throw new Error("学習セットの問題数が不正です。");
    const seen = new Set();
    return items.map((item) => {
      if (!ownKeys(item, ["itemId", "revision", "kind"]) || !validToken(item.itemId) ||
          !validToken(item.revision) || !["review", "new"].includes(item.kind) || seen.has(item.itemId)) {
        throw new Error("学習セットの問題データが不正です。");
      }
      seen.add(item.itemId);
      return { ...item };
    });
  }

  function validateSession(state) {
    if (!ownKeys(state, ["version", "tier", "mode", "createdAt", "day", "items", "index", "done"]) || state.version !== 1) {
      throw new Error("保存済み学習セットの形式が不正です。");
    }
    checkSettings(state.tier, state.mode);
    checkDay(state.day);
    const date = new Date(state.createdAt);
    if (typeof state.createdAt !== "string" || !Number.isFinite(date.getTime()) || date.toISOString() !== state.createdAt) {
      throw new Error("保存済み学習セットの日時が不正です。");
    }
    const items = validateSelection(state.items);
    if (!Number.isInteger(state.index) || state.index < 0 || state.index > items.length ||
        !Array.isArray(state.done) || new Set(state.done).size !== state.done.length ||
        state.done.some((id) => !items.some((item) => item.itemId === id))) {
      throw new Error("保存済み学習セットの途中位置・完了状態が不正です。");
    }
    return { ...state, items, done: [...state.done] };
  }

  function createSession({ items, tier = 1, mode = "mixed", now = () => new Date() }) {
    const date = new Date(typeof now === "function" ? now() : now);
    if (!Number.isFinite(date.getTime())) throw new Error("学習セットの作成日時が不正です。");
    return validateSession({ version: 1, tier, mode, createdAt: date.toISOString(),
      day: historyApi().localDay(date), items, index: 0, done: [] });
  }

  function setIndex(state, index) {
    return validateSession({ ...validateSession(state), index });
  }

  function markDone(state, itemId) {
    const value = validateSession(state);
    return validateSession({ ...value, done: [...new Set([...value.done, itemId])] });
  }

  function reconcileSession(state, items) {
    const value = validateSession(state);
    const current = new Map(catalogItems(items).map((item) => [item.itemId, item]));
    let changed = false;
    const done = new Set(value.done);
    const selected = value.items.flatMap((item) => {
      const latest = current.get(item.itemId);
      if (!latest || latest.tier > value.tier) {
        changed = true;
        done.delete(item.itemId);
        return [];
      }
      if (latest.revision !== item.revision) {
        changed = true;
        done.delete(item.itemId);
        return [{ ...item, revision: latest.revision, kind: "new" }];
      }
      return [item];
    });
    const firstPending = selected.findIndex((item) => !done.has(item.itemId));
    const index = changed ? (firstPending === -1 ? selected.length : firstPending) : value.index;
    return validateSession({ ...value, items: selected, done: [...done], index });
  }

  function summarizeProgress({ items, events, day = historyApi().localDay(new Date()) }) {
    checkDay(day);
    const history = indexedEvents(events);
    const emptyCounts = () => ({ total: 0, unanswered: 0, review: 0, priority: 0, todayAnswered: 0, todayReview: 0 });
    const result = { ...emptyCounts(), byTier: { 1: emptyCounts(), 2: emptyCounts(), 3: emptyCounts() },
      bySection: Object.create(null) };
    for (const item of catalogItems(items)) {
      const status = itemStatus(item, history, day);
      if (!result.bySection[item.section]) result.bySection[item.section] = { ...emptyCounts(), group: item.group };
      for (const counts of [result, result.byTier[item.tier], result.bySection[item.section]]) {
        counts.total += 1;
        counts.unanswered += Number(status.unanswered);
        counts.review += Number(status.review);
        counts.priority += Number(status.priority);
        counts.todayAnswered += Number(status.answeredToday);
        counts.todayReview += Number(status.review && !status.exposedToday);
      }
    }
    return result;
  }

  function createStore({ storage }) {
    function read() {
      try {
        const raw = storage.getItem(STORAGE_KEY);
        return raw === null ? null : validateSession(JSON.parse(raw));
      } catch (error) {
        throw new Error(`保存済み学習セットを読み取れません。データは消去していません。${error.message}`);
      }
    }
    function write(state) {
      const value = validateSession(state);
      read(); // Never replace unreadable saved data, including from another tab.
      try { storage.setItem(STORAGE_KEY, JSON.stringify(value)); }
      catch { throw new Error("学習セットを保存できません。ブラウザの保存制限・空き容量を確認してください。今回の変更は未保存です。"); }
      return value;
    }
    function clear() {
      try { storage.removeItem(STORAGE_KEY); }
      catch { throw new Error("学習セットを削除できません。保存済みデータは変更していません。"); }
    }
    return { read, write, clear };
  }

  const api = Object.freeze({ STORAGE_KEY, MAX_ITEMS, selectItems, createSession, validateSession,
    setIndex, markDone, reconcileSession, summarizeProgress, createStore });
  scope.ArchitectStudySession = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(globalThis);
