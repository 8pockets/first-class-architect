// Run through Playwright MCP browser_run_code_unsafe({ filename: "tests/browser-history.acceptance.js" }).
// Prerequisite: build _site, then python -m http.server 8765 --bind 127.0.0.1 --directory _site.
// All history is written inside fresh isolated browser contexts, never the user's browser profile.
async (page) => {
  const browser = page.context().browser();
  const base = "http://127.0.0.1:8765/";
  const production = "https://8pockets.github.io/first-class-architect/";
  const prefix = "architect-steel-history:v1:event:";
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  const results = [];

  for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport, timezoneId: "Asia/Tokyo", acceptDownloads: true });
    const errors = [];
    const requests = [];
    let revisionOverride = false;
    try {
      await context.route(`${base}**`, async (route) => {
        if (route.request().url().endsWith("/favicon.ico")) { await route.fulfill({ status: 204 }); return; }
        const response = await route.fetch();
        if (response.headers()["content-type"]?.includes("text/html")) {
          let html = (await response.text()).split(production).join(base);
          if (revisionOverride) html = html.replace(/data-question-revision="[a-f0-9]{64}"/, `data-question-revision="${"f".repeat(64)}"`);
          await route.fulfill({ response, body: html });
        } else await route.fulfill({ response });
      });
      await context.addInitScript(() => {
        const NativeDate = Date;
        window.__historyTestNow = Number(sessionStorage.getItem("history-test-clock")) || Date.parse("2026-10-06T03:00:00.000Z");
        window.__setHistoryTestDay = (day) => {
          window.__historyTestNow = Date.parse(`2026-10-${String(day).padStart(2, "0")}T03:00:00.000Z`);
          sessionStorage.setItem("history-test-clock", String(window.__historyTestNow));
        };
        window.Date = class extends NativeDate {
          constructor(...args) { super(...(args.length ? args : [window.__historyTestNow])); }
          static now() { return window.__historyTestNow; }
        };
        const save = Storage.prototype.setItem;
        Storage.prototype.setItem = function (key, value) {
          if (window.__failHistoryStorage && key.startsWith("architect-steel-history:")) throw new DOMException("Quota exceeded", "QuotaExceededError");
          return save.call(this, key, value);
        };
      });
      const view = await context.newPage();
      view.on("pageerror", (error) => errors.push(error.message));
      view.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
      context.on("request", (request) => requests.push({ url: request.url(), method: request.method() }));
      await view.goto(base, { waitUntil: "networkidle" });
      const cards = view.locator(".principle-card");
      const inventory = await cards.evaluateAll((elements) => elements.map((card) => ({
        id: card.dataset.studyId, revision: card.dataset.questionRevision,
        correct: card.dataset.correctChoice, tier: card.dataset.coverageTier, type: card.dataset.type,
      })));
      check(inventory.length > 0, "No study cards loaded");
      check(await view.evaluate(() => Boolean(window.ArchitectAnswerHistory)), "History asset did not initialize");
      check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "Horizontal overflow at initial viewport");
      const diagramStyles = await view.locator(".question-figure svg").evaluateAll((figures) => figures.map((svg) => {
        const rect = svg.getBoundingClientRect(), style = getComputedStyle(svg);
        return { width: rect.width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
          height: rect.height - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom),
          background: style.backgroundColor, color: style.color };
      }));
      check(diagramStyles.length >= 2, "Expected both original diagram question variants");
      check(diagramStyles.every((svg) => Math.abs(svg.width / svg.height - 560 / 230) < 0.03), "Diagram aspect ratio was distorted");
      check(diagramStyles.every((svg) => svg.background === "rgb(255, 255, 255)" && svg.color !== "rgb(255, 255, 255)"), "Diagram axes/curves lost their contrasting white surface");
      check(await view.locator("[data-answer-disclosure][open]").count() === 0, "Answers must start closed");
      const first = inventory[0];
      const cardFor = (item, tab = view) => tab.locator(`[data-study-id="${item.id}"]`);
      const answers = async (item, tab = view) => tab.evaluate(({ prefix, id }) => Object.keys(localStorage)
        .filter((key) => key.startsWith(prefix)).map((key) => JSON.parse(localStorage.getItem(key)))
        .filter((event) => event.type === "answer" && (!id || event.itemId === id)), { prefix, id: item?.id });
      const choose = async (item, right, tab = view) => {
        const choice = right ? item.correct : item.correct === "A" ? "B" : "A";
        await cardFor(item, tab).locator(`[data-answer-choice="${choice}"]`).click();
      };
      const wrong = first.correct === "A" ? "B" : "A";
      await cardFor(first).locator("[data-answer-history] summary").click();
      check((await answers(first)).length === 0, "An empty history panel counted as an answer");
      await cardFor(first).locator(`[data-answer-choice="${wrong}"]`).focus();
      await view.keyboard.press("Enter");
      await choose(first, true);
      await choose(first, false);
      let log = await answers(first);
      check(log.length === 1 && log[0].choice === wrong && log[0].independent, "First choice or keyboard was double-counted");
      check((await cardFor(first).locator("[data-answer-result]").innerText()).includes("要復習"), "First independent error should require review");
      await cardFor(first).locator("[data-answer-retry]").click();
      await choose(first, true);
      log = await answers(first);
      check(log.length === 2 && log.some((entry) => entry.correct && !entry.independent), "Retry must remain assisted today");
      await view.reload({ waitUntil: "networkidle" });
      await choose(first, true);
      log = await answers(first);
      check(log.length === 3 && log.filter((entry) => entry.independent).length === 1, "Reload erased exposure evidence");

      for (const [day, right, expected] of [[7, false, "重点復習"], [8, true, "要復習"], [9, true, "正解"]]) {
        // Advance on the next document, not while yesterday's answer remains
        // on screen (which would correctly count as seeing today's answer).
        await view.evaluate((day) => sessionStorage.setItem("history-test-clock",
          String(Date.parse(`2026-10-${String(day).padStart(2, "0")}T03:00:00.000Z`))), day);
        await view.reload({ waitUntil: "networkidle" });
        await choose(first, right);
        const result = await cardFor(first).locator("[data-answer-result]").innerText();
        check(result.includes(expected), `Day ${day} review status incorrect: ${result}`);
      }

      const second = inventory.find((item) => item.tier === "2" && item.id !== first.id);
      await choose(second, false);
      await view.locator("#review-filter").selectOption("review");
      await view.locator("#coverage-filter").selectOption("core-only");
      check(await view.locator(".principle-card:not([hidden])").count() === 0, "Coverage/review filters must intersect");
      await view.locator("#coverage-filter").selectOption("standard-only");
      await view.locator("#catalog-search").fill(second.id);
      check(await view.locator(".principle-card:not([hidden])").count() === 1, "Search/review/coverage intersection lost its card");
      const otherType = ["principle", "rule", "identification"].find((type) => type !== second.type);
      await view.locator(`[data-filter-type="${otherType}"]`).click();
      check(await view.locator(".principle-card:not([hidden])").count() === 0, "Type filtering must intersect history filtering");
      await view.locator("#reset-filters").click();
      check(await view.locator(".principle-card:not([hidden])").count() === inventory.length, "Reset did not restore all cards");

      const fresh = inventory.find((item) => ![first.id, second.id].includes(item.id));
      await view.locator("#review-filter").selectOption("unanswered");
      await choose(fresh, false);
      check(!(await cardFor(fresh).evaluate((card) => card.hidden)), "A card vanished while answering");
      await view.locator("#review-filter").selectOption("review");
      await view.locator("#review-filter").selectOption("unanswered");
      check(await cardFor(fresh).evaluate((card) => card.hidden), "Explicit filter refresh did not update answer history");
      await view.locator("#reset-filters").click();

      await view.locator("#coverage-filter").selectOption("core-only");
      await view.locator("#toggle-visible-answers").click();
      const bulk = await cards.evaluateAll((elements) => elements.map((card) => ({ hidden: card.hidden,
        open: card.querySelector("[data-answer-disclosure]").open })));
      check(bulk.every((card) => card.open === !card.hidden), "Bulk opening changed a hidden card or skipped a visible one");
      await view.locator("#toggle-visible-answers").click();
      check(await view.locator("[data-answer-disclosure][open]").count() === 0, "Bulk closing left an answer open");
      await view.locator("#reset-filters").click();

      await cardFor(inventory[0]).locator("[data-answer-disclosure] summary").click();
      const lowerChoice = cardFor(inventory[1]).locator("[data-answer-choice]").first();
      await lowerChoice.scrollIntoViewIfNeeded();
      const beforeY = await view.evaluate(() => scrollY);
      await lowerChoice.click();
      const afterY = await view.evaluate(() => scrollY);
      check(await cardFor(inventory[0]).locator("[data-answer-disclosure]").evaluate((element) => element.open), "Lower answer collapsed the answer above");
      check(Math.abs(beforeY - afterY) <= 2, `Answer choice moved viewport: ${beforeY} -> ${afterY}`);
      check(await view.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "Horizontal overflow after answering");

      const [download] = await Promise.all([view.waitForEvent("download"), view.locator("#history-export").click()]);
      const stream = await download.createReadStream();
      let backup = "";
      for await (const chunk of stream) backup += chunk.toString("utf8");
      const archive = JSON.parse(backup);
      check(archive.format === "architect-steel-answer-history" && archive.events.length > 0, "Export is not a valid history archive");
      const countBeforeImport = (await answers()).length;
      await view.locator("#history-import").setInputFiles({ name: "history.json", mimeType: "application/json", buffer: Buffer.from(backup) });
      await view.waitForFunction(() => document.querySelector("#history-status").textContent.includes("0件の履歴を追加"));
      check((await answers()).length === countBeforeImport, "Backup import duplicated existing answers");
      const importedItem = inventory.at(-1);
      const importedEvent = { ...archive.events.find((event) => event.type === "answer"),
        id: "acceptance-import-event", attemptId: "acceptance-import-attempt", sessionId: "acceptance-import-session",
        itemId: importedItem.id, revision: importedItem.revision,
        choice: importedItem.correct, correctChoice: importedItem.correct, correct: true, independent: true };
      const additionalArchive = JSON.stringify({ ...archive, events: [importedEvent] });
      const originalIds = (await answers()).map((event) => event.id);
      await view.locator("#history-import").setInputFiles({ name: "additional.json", mimeType: "application/json", buffer: Buffer.from(additionalArchive) });
      await view.waitForFunction(() => document.querySelector("#history-status").textContent.includes("1件の履歴を追加"));
      const mergedAnswers = await answers();
      check(mergedAnswers.length === countBeforeImport + 1 && originalIds.every((id) => mergedAnswers.some((event) => event.id === id)), "Import replaced rather than merged existing history");
      await view.locator("#history-import").setInputFiles({ name: "invalid.json", mimeType: "application/json", buffer: Buffer.from('{"format":"wrong","events":[]}') });
      await view.waitForFunction(() => document.querySelector("#history-status").dataset.error === "true");
      check((await answers()).length === countBeforeImport + 1, "Invalid import changed history");

      const otherTab = await context.newPage();
      await otherTab.goto(base, { waitUntil: "networkidle" });
      await otherTab.evaluate(() => window.__setHistoryTestDay(9));
      const tabItem = inventory.find((item) => item.tier === "3" && ![first.id, second.id, fresh.id, importedItem.id].includes(item.id));
      await choose(tabItem, false, otherTab);
      check((await answers(tabItem)).length === 1, "A second tab's appended answer was lost");
      await otherTab.close();

      const countBeforeRevision = (await answers(first)).length;
      revisionOverride = true;
      await view.reload({ waitUntil: "networkidle" });
      check(await cardFor(first).getAttribute("data-question-revision") === "f".repeat(64), "Revision test override was not applied");
      const revisedResult = await cardFor(first).locator("[data-answer-result]").innerText();
      await cardFor(first).locator(".card-tools > summary").click();
      const revisedDetails = await cardFor(first).locator("[data-answer-status-details]").innerText();
      check(revisedResult === "未回答" && revisedDetails.includes("旧版の回答"), "Old revision answers contaminated current grading");
      await choose(first, true);
      const afterRevision = await answers(first);
      check(afterRevision.length === countBeforeRevision + 1, "Revision lost historical records");
      check(afterRevision.some((event) => event.revision === "f".repeat(64) && event.independent), "A new revision should have a fresh independent first answer");

      await cardFor(first).locator("[data-answer-choice]").first().evaluate((choice) => choice.setAttribute("aria-pressed", "true"));
      await view.emulateMedia({ media: "print" });
      const print = await cardFor(first).evaluate((card) => ({
        answer: getComputedStyle(card.querySelector("[data-answer-disclosure]")).display,
        history: getComputedStyle(card.querySelector("[data-answer-history]")).display,
        result: getComputedStyle(card.querySelector("[data-answer-result]")).display,
        retry: getComputedStyle(card.querySelector("[data-answer-retry]")).display,
        color: getComputedStyle(card.querySelector('[data-answer-choice][aria-pressed="true"]')).color,
        background: getComputedStyle(card.querySelector('[data-answer-choice][aria-pressed="true"]')).backgroundColor,
        border: getComputedStyle(card.querySelector('[data-answer-choice][aria-pressed="true"]')).borderTopWidth,
      }));
      check([print.answer, print.history, print.result, print.retry].every((display) => display === "none"), "Private history or answer content leaked to print");
      check(print.color === "rgb(0, 0, 0)" && print.background === "rgba(0, 0, 0, 0)" && print.border === "0px", "Selection styling leaked to question-only print");
      await view.emulateMedia({ media: "screen" });

      const answeredIds = new Set((await answers()).map((event) => event.itemId));
      const quotaItem = inventory.find((item) => !answeredIds.has(item.id));
      await view.evaluate(() => { window.__failHistoryStorage = true; });
      await choose(quotaItem, false);
      check((await answers(quotaItem)).length === 0, "Failed storage reported a saved answer");
      check(await view.locator("#history-status").getAttribute("data-error") === "true", "Storage errors were not visible");
      check((await cardFor(quotaItem).locator("[data-answer-result]").innerText()).includes("保存されていません"), "The unsaved answer was not clearly marked");
      check(await cardFor(quotaItem).locator("[data-answer-disclosure]").evaluate((element) => element.open), "Storage failure blocked answer reading");
      await view.evaluate(() => { window.__failHistoryStorage = false; });
      await cardFor(quotaItem).locator("[data-answer-retry]").click();
      await choose(quotaItem, true);
      const quotaLog = await answers(quotaItem);
      check(quotaLog.length === 1 && !quotaLog[0].independent, "Retry after a storage failure should remain assisted, not erase answer exposure");
      const viewedDuringFailure = inventory.find((item) => !answeredIds.has(item.id) && item.id !== quotaItem.id);
      await view.evaluate(() => { window.__failHistoryStorage = true; });
      await cardFor(viewedDuringFailure).locator("[data-answer-disclosure] summary").click();
      await cardFor(viewedDuringFailure).locator("[data-answer-disclosure] summary").click();
      await view.evaluate(() => { window.__failHistoryStorage = false; });
      await choose(viewedDuringFailure, true);
      const recoveredViewLog = await answers(viewedDuringFailure);
      check(recoveredViewLog.length === 1 && !recoveredViewLog[0].independent, "Closing an answer viewed during storage failure erased its in-session exposure");
      check(errors.length === 0, `Browser errors: ${errors.join("; ")}`);
      check(requests.every((request) => request.method === "GET" && request.url.startsWith(base)), "History caused an outbound or mutating network request");
      results.push({ viewport, cards: inventory.length, answerEvents: (await answers()).length,
        backupEvents: archive.events.length, scrollDelta: afterY - beforeY,
        browserErrors: errors.length, networkRequests: requests.length, passed: true });
    } finally { await context.close(); }
  }
  return results;
}
