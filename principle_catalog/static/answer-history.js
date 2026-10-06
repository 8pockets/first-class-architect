/* Browser-local, append-only answer history. No server or repository writes. */
((scope) => {
  "use strict";

  const PREFIX = "architect-steel-history:v1:event:";
  const FORMAT = "architect-steel-answer-history";
  const MAX_EVENTS = 100000;
  const MAX_IMPORT_BYTES = 20 * 1024 * 1024;
  const validToken = (value) =>
    typeof value === "string" && /^[a-zA-Z0-9._:-]{1,200}$/.test(value);
  const localDay = (date) =>
    `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  // Clock precision is one millisecond: a rapid assisted retry must not sort ahead
  // of the independent first answer simply because its random UUID is smaller.
  const order = (a, b) => a.at.localeCompare(b.at) ||
    (a.type === "view" ? 0 : 1) - (b.type === "view" ? 0 : 1) ||
    Number(Boolean(b.independent)) - Number(Boolean(a.independent)) || a.id.localeCompare(b.id);
  const canonical = (event) => JSON.stringify(Object.fromEntries(
    Object.entries(event).sort(([a], [b]) => a.localeCompare(b)),
  ));

  function validateEvent(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("回答履歴の形式が不正です。");
    }
    const baseKeys = ["version", "type", "id", "itemId", "revision", "at", "day", "offsetMinutes", "sessionId"];
    const answerKeys = ["attemptId", "choice", "correctChoice", "correct", "independent"];
    const keys = value.type === "answer" ? [...baseKeys, ...answerKeys] : baseKeys;
    const date = new Date(value.at);
    const offsetValid = Number.isInteger(value.offsetMinutes) && Math.abs(value.offsetMinutes) <= 840;
    const recordedDay = offsetValid && Number.isFinite(date.getTime())
      ? new Date(date.getTime() - value.offsetMinutes * 60000).toISOString().slice(0, 10)
      : null;
    if (value.version !== 1 || !["view", "answer"].includes(value.type) ||
        ![value.id, value.itemId, value.revision, value.sessionId].every(validToken) ||
        typeof value.at !== "string" || !Number.isFinite(date.getTime()) || date.toISOString() !== value.at ||
        !offsetValid || value.day !== recordedDay ||
        Object.keys(value).length !== keys.length || keys.some((key) => !Object.hasOwn(value, key))) {
      throw new Error("回答履歴の識別子・日時・形式が不正です。");
    }
    if (value.type === "answer" &&
        (!validToken(value.attemptId) || !["A", "B"].includes(value.choice) ||
         !["A", "B"].includes(value.correctChoice) || typeof value.independent !== "boolean" ||
         value.correct !== (value.choice === value.correctChoice))) {
      throw new Error("回答履歴の採点データが不正です。");
    }
    return { ...value };
  }

  function mergeEvents(...collections) {
    const indexed = new Map();
    const attempts = new Map();
    for (const values of collections) {
      if (!Array.isArray(values) || values.length > MAX_EVENTS) throw new Error("回答履歴の件数が上限を超えています。");
      for (const value of values) {
        const event = validateEvent(value);
        const old = indexed.get(event.id);
        if (old && canonical(old) !== canonical(event)) throw new Error("同じ履歴IDの内容が異なります。既存の履歴は変更しません。");
        if (event.type === "answer") {
          const priorAttempt = attempts.get(event.attemptId);
          if (priorAttempt && canonical(priorAttempt) !== canonical(event)) throw new Error("同じ回答試行に複数の記録があります。既存の履歴は変更しません。");
          attempts.set(event.attemptId, event);
        }
        indexed.set(event.id, event);
      }
    }
    if (indexed.size > MAX_EVENTS) throw new Error("回答履歴の件数が上限を超えています。");
    return [...indexed.values()].sort(order);
  }

  function parseBackup(json) {
    if (typeof json !== "string" || json.length > MAX_IMPORT_BYTES) throw new Error("履歴ファイルは20 MB以下にしてください。");
    let backup;
    try { backup = JSON.parse(json); } catch { throw new Error("履歴ファイルをJSONとして読み取れません。"); }
    if (!backup || backup.format !== FORMAT || backup.version !== 1 || !Array.isArray(backup.events)) {
      throw new Error("このサイトの回答履歴バックアップではありません。");
    }
    return mergeEvents(backup.events);
  }

  function summarize(events, itemId, revision) {
    const related = events.filter((event) => event.itemId === itemId);
    const current = related.filter((event) => event.revision === revision).sort(order);
    const answers = current.filter((event) => event.type === "answer");
    const oldAnswers = related.filter((event) => event.type === "answer" && event.revision !== revision).sort(order);
    const exposedDays = new Set();
    const independentAnswers = [];
    for (const event of current) {
      if (event.type === "answer" && event.independent && !exposedDays.has(event.day)) independentAnswers.push(event);
      exposedDays.add(event.day);
    }
    let review = false;
    let wrongStreak = 0;
    let recoveryDays = [];
    for (const answer of independentAnswers) {
      if (!answer.correct) {
        review = true;
        wrongStreak += 1;
        recoveryDays = [];
      } else {
        wrongStreak = 0;
        if (review && !recoveryDays.includes(answer.day)) recoveryDays.push(answer.day);
        if (recoveryDays.length >= 2) review = false;
      }
    }
    return {
      answers, oldAnswers, independentAnswers,
      latest: answers.at(-1) ?? null,
      unanswered: answers.length === 0,
      hasHistory: answers.length + oldAnswers.length > 0,
      review, priority: review && wrongStreak >= 2, wrongStreak,
      recoveryDays: review ? recoveryDays.length : 0,
    };
  }

  function matchesFilter(summary, filter) {
    if (filter === "unanswered") return summary.unanswered;
    if (filter === "review") return summary.review;
    if (filter === "priority") return summary.priority;
    if (filter === "history") return summary.hasHistory;
    return filter === "all";
  }

  function createStore({ storage, now = () => new Date(), uuid, sessionId }) {
    const makeId = uuid;
    if (typeof makeId !== "function" || !validToken(sessionId)) throw new Error("回答履歴を初期化できません。");
    function read() {
      const values = [];
      try {
        for (let i = 0; i < storage.length; i += 1) {
          const key = storage.key(i);
          if (!key?.startsWith(PREFIX)) continue;
          const raw = storage.getItem(key);
          if (raw === null) continue;
          const event = validateEvent(JSON.parse(raw));
          if (key !== PREFIX + event.id) throw new Error("履歴IDが一致しません。");
          values.push(event);
        }
        return mergeEvents(values);
      } catch (error) {
        throw new Error(`保存済みの回答履歴を読み取れません。データは消去していません。${error.message}`);
      }
    }
    function save(event) {
      validateEvent(event);
      const events = read(); // Every write sees other tabs' latest entries.
      const existing = events.find((candidate) => candidate.id === event.id);
      mergeEvents(events, [event]); // Detect ID conflicts before any mutation.
      if (existing) return existing;
      try { storage.setItem(PREFIX + event.id, JSON.stringify(event)); }
      catch { throw new Error("回答履歴を保存できません。ブラウザの保存制限・空き容量を確認してください。今回の記録は未保存です。"); }
      return event;
    }
    function base(type, itemId, revision) {
      const date = now();
      return { version: 1, type, id: makeId(), itemId, revision, at: date.toISOString(),
        day: localDay(date), offsetMinutes: date.getTimezoneOffset(), sessionId };
    }
    function view(itemId, revision) {
      const event = base("view", itemId, revision);
      const existing = read().find((entry) => entry.itemId === itemId && entry.revision === revision && entry.day === event.day);
      return existing ?? save(event);
    }
    function answer({ itemId, revision, attemptId, choice, correctChoice }) {
      const event = base("answer", itemId, revision);
      const events = read();
      const existing = events.find((entry) => entry.type === "answer" && entry.attemptId === attemptId);
      if (existing) {
        if (existing.itemId !== itemId || existing.revision !== revision) throw new Error("回答試行IDが競合しています。");
        return existing;
      }
      const independent = !events.some((entry) => entry.itemId === itemId && entry.revision === revision && entry.day === event.day);
      return save({ ...event, attemptId, choice, correctChoice, correct: choice === correctChoice, independent });
    }
    function importBackup(json) {
      const incoming = parseBackup(json);
      const existing = read();
      mergeEvents(existing, incoming); // All validation happens before first write.
      const existingIds = new Set(existing.map((event) => event.id));
      let added = 0;
      for (const event of incoming) {
        if (!existingIds.has(event.id)) {
          try {
            // Per-event keys make this append safe across tabs without a quadratic full-store scan.
            const concurrent = storage.getItem(PREFIX + event.id);
            if (concurrent !== null) {
              if (canonical(validateEvent(JSON.parse(concurrent))) !== canonical(event)) throw new Error("同じ履歴IDの内容が異なります。");
            } else {
              storage.setItem(PREFIX + event.id, JSON.stringify(event));
              added += 1;
            }
          }
          catch (error) { throw new Error(`${added}件を追加した時点で復元を中断しました。既存の履歴は保持されています。${error.message}`); }
        }
      }
      return added;
    }
    return {
      read, view, answer, importBackup,
      exportBackup: () => JSON.stringify({ format: FORMAT, version: 1, exportedAt: now().toISOString(), events: read() }, null, 2),
    };
  }

  scope.ArchitectAnswerHistory = Object.freeze({ PREFIX, MAX_IMPORT_BYTES, createStore, validateEvent,
    parseBackup, mergeEvents, summarize, matchesFilter, localDay, compareEvents: order });
})(globalThis);
