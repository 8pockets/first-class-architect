/* Optional transfer practice has its own IDs; it never clears a core review. */
(() => {
  "use strict";
  const history = globalThis.ArchitectAnswerHistory;
  const panels = [...document.querySelectorAll("[data-practice-panel]")];
  if (!history || !panels.length) return;
  let store;
  const uuid = () => globalThis.crypto.randomUUID();
  try { store = history.createStore({ storage: window.localStorage, uuid, sessionId: uuid() }); }
  catch { /* Answers stay available even if storage is blocked. */ }
  const metadata = (panel) => ({ itemId: panel.dataset.practiceId, revision: panel.dataset.practiceRevision,
    correctChoice: panel.dataset.correctChoice });
  const render = (panel) => {
    if (!store) return;
    try {
      const summary = history.summarize(store.read(), panel.dataset.practiceId, panel.dataset.practiceRevision);
      const entries = [...summary.answers, ...summary.oldAnswers].sort((a, b) => history.compareEvents(b, a));
      const rows = entries.slice(0, 10).map((event) => {
        const row = document.createElement("li");
        row.textContent = `${event.day} · ${event.choice} → ${event.correct ? "正解" : "不正解"} · 追加練習` +
          (event.revision === panel.dataset.practiceRevision ? "" : "（旧版）");
        return row;
      });
      if (!rows.length) {
        const row = document.createElement("li"); row.textContent = "まだ追加確認の記録はありません。"; rows.push(row);
      }
      panel.querySelector("[data-practice-history-list]").replaceChildren(...rows);
    } catch (error) {
      panel.querySelector("[data-practice-result]").textContent = `追加確認の履歴を読み取れません。${error.message}`;
    }
  };
  for (const panel of panels) {
    const answer = panel.querySelector("[data-practice-answer]");
    const result = panel.querySelector("[data-practice-result]");
    const choices = [...panel.querySelectorAll("[data-practice-choice]")];
    let answered = false;
    const retry = document.createElement("button");
    retry.type = "button"; retry.className = "answer-retry"; retry.textContent = "追加確認をもう一度"; retry.hidden = true;
    result.after(retry);
    const log = document.createElement("details"); log.className = "practice-history";
    const heading = document.createElement("summary"); heading.textContent = "追加確認の履歴";
    const list = document.createElement("ul"); list.dataset.practiceHistoryList = "";
    log.append(heading, list); panel.querySelector(".practice-body").append(log);
    const sync = () => choices.forEach((choice) => choice.setAttribute("aria-expanded", String(answer.open)));
    answer.addEventListener("toggle", sync);
    for (const choice of choices) {
      choice.addEventListener("click", () => {
        if (answered) return;
        answered = true; retry.hidden = false;
        const selected = choice.dataset.practiceChoice;
        const correct = selected === panel.dataset.correctChoice;
        result.textContent = `${selected} → ${correct ? "正解" : "不正解"}。追加練習として記録します。本体の成績・復習解除には含めません。`;
        try {
          if (!store) throw new Error("ブラウザの保存機能を利用できません。");
          const { itemId, revision } = metadata(panel);
          // These questions are reached from the parent's explanation, so they
          // are always assisted practice, never independent mastery evidence.
          store.view(itemId, revision);
          store.answer({ ...metadata(panel), choice: selected, attemptId: uuid() });
          render(panel);
          globalThis.ArchitectCatalog?.refreshHistory();
        } catch (error) { result.textContent = `${selected} → ${correct ? "正解" : "不正解"}。今回の追加確認は未保存です。${error.message}`; }
        answer.open = true; sync();
        choices.forEach((button) => { button.disabled = true; });
      });
    }
    retry.addEventListener("click", () => {
      answered = false; answer.open = false; sync(); retry.hidden = true;
      choices.forEach((choice) => { choice.disabled = false; });
      result.textContent = "追加練習です。本体の成績とは別に記録します。";
      choices[0]?.focus();
    });
    render(panel);
  }
  document.addEventListener("architect:history", () => panels.forEach(render));
})();
