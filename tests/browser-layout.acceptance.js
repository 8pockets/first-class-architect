// Run through Playwright MCP browser_run_code_unsafe({ filename: "tests/browser-layout.acceptance.js" }).
// Prerequisite: build _site, then python -m http.server 8765 --bind 127.0.0.1 --directory _site.
// Fresh isolated contexts keep bulk answer-view records out of the user's browser profile.
async (page) => {
  const browser = page.context().browser();
  const base = "http://127.0.0.1:8765/";
  const production = "https://8pockets.github.io/first-class-architect/";
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  const results = [];

  for (const width of [320, 390, 768, 1280]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, timezoneId: "Asia/Tokyo" });
    const errors = [];
    try {
      // Exercise the current generated assets, never an older deployed stylesheet.
      await context.route(`${base}**`, async (route) => {
        if (route.request().url().endsWith("/favicon.ico")) {
          await route.fulfill({ status: 204 });
          return;
        }
        const response = await route.fetch();
        if (response.headers()["content-type"]?.includes("text/html")) {
          await route.fulfill({ response, body: (await response.text()).split(production).join(base) });
        } else await route.fulfill({ response });
      });
      const view = await context.newPage();
      view.on("pageerror", (error) => errors.push(error.message));
      await view.goto(base, { waitUntil: "networkidle" });
      const inventory = await view.locator(".principle-card").count();
      check(inventory > 0, `${width}px: no study cards loaded`);
      check(await view.evaluate(() => Boolean(window.ArchitectAnswerHistory)), `${width}px: current local history asset not loaded`);

      const noDocumentOverflow = async (stage) => {
        const geometry = await view.evaluate(() => ({
          viewport: innerWidth,
          document: document.documentElement.scrollWidth,
          body: document.body.scrollWidth,
        }));
        check(Math.max(geometry.document, geometry.body) <= geometry.viewport + 1,
          `${width}px: horizontal overflow ${stage}: ${JSON.stringify(geometry)}`);
      };
      await noDocumentOverflow("initially");

      const scope = view.locator(".exam-scope");
      check(await scope.count() === 1, `${width}px: exam coverage panel missing`);
      check(!(await scope.evaluate((element) => element.open)), `${width}px: coverage panel should start closed`);
      await scope.locator("summary").click();
      check(await scope.evaluate((element) => element.open), `${width}px: header decoration blocked coverage disclosure`);
      const scopeLayout = await scope.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        const header = element.closest(".site-header").getBoundingClientRect();
        const summary = element.querySelector("summary").getBoundingClientRect();
        return {
          insideHeader: rect.left >= header.left && rect.right <= header.right,
          summaryHeight: summary.height,
          childInsets: [...element.children].map((child) => {
            const childRect = child.getBoundingClientRect();
            return { left: childRect.left - rect.left, right: rect.right - childRect.right };
          }),
        };
      });
      check(scopeLayout.insideHeader && scopeLayout.summaryHeight >= 44,
        `${width}px: coverage panel or summary does not fit: ${JSON.stringify(scopeLayout)}`);
      check(scopeLayout.childInsets.every((inset) => inset.left >= 16 && inset.right >= 16),
        `${width}px: coverage content lost horizontal padding: ${JSON.stringify(scopeLayout)}`);
      await noDocumentOverflow("with coverage panel open");
      await scope.locator("summary").click();
      check(!(await scope.evaluate((element) => element.open)), `${width}px: coverage panel did not close`);

      await view.locator("#toggle-visible-answers").click();
      check(await view.locator("[data-answer-disclosure][open]").count() === inventory,
        `${width}px: bulk open did not expose all answer content`);
      const layout = await view.evaluate(() => {
        const failures = [];
        let checkedChildren = 0;
        let checkedSources = 0;
        const fail = (condition, message) => { if (!condition) failures.push(message); };
        const tolerance = 1;
        const numeric = (value) => Number.parseFloat(value) || 0;
        const within = (rect, left, right) => rect.left >= left - tolerance && rect.right <= right + tolerance;

        for (const card of document.querySelectorAll(".principle-card")) {
          const id = card.dataset.studyId;
          const cardRect = card.getBoundingClientRect();
          const content = card.querySelector(".answer-content");
          const contentRect = content.getBoundingClientRect();
          const style = getComputedStyle(content);
          const cardStyle = getComputedStyle(card);
          const paddingLeft = numeric(style.paddingLeft);
          const paddingRight = numeric(style.paddingRight);
          const paddingBottom = numeric(style.paddingBottom);
          const insetStart = numeric(cardStyle.getPropertyValue("--card-inset-start"));
          const insetEnd = numeric(cardStyle.getPropertyValue("--card-inset-end"));
          const left = contentRect.left + paddingLeft;
          const right = contentRect.right - paddingRight;
          fail(paddingLeft >= 16 && paddingRight >= 16 && paddingBottom >= 16,
            `${id}: answer container padding disappeared`);
          for (const child of content.children) {
            const rect = child.getBoundingClientRect();
            if (!rect.width || !rect.height) continue;
            checkedChildren += 1;
            fail(within(rect, left, right), `${id}: ${child.className || child.tagName} escaped answer content box`);
            fail(within(rect, cardRect.left + insetStart, cardRect.right - insetEnd),
              `${id}: ${child.className || child.tagName} lost card-side insets`);
          }
          const firstChild = content.firstElementChild.getBoundingClientRect();
          fail(Math.abs(firstChild.left - left) <= tolerance,
            `${id}: title inherited duplicate horizontal padding`);
          const lastChild = content.lastElementChild.getBoundingClientRect();
          fail(contentRect.bottom - lastChild.bottom >= paddingBottom - tolerance,
            `${id}: final answer block lost bottom padding`);

          for (const list of content.querySelectorAll(".authority-sources")) {
            checkedSources += 1;
            const listRect = list.getBoundingClientRect();
            fail(within(listRect, left, right), `${id}: authority source panel escaped answer content`);
            for (const item of list.children) {
              const itemRect = item.getBoundingClientRect();
              fail(within(itemRect, listRect.left + 16, listRect.right - 16),
                `${id}: authority source text lost panel padding`);
            }
            const lastItem = list.lastElementChild.getBoundingClientRect();
            fail(listRect.bottom - lastItem.bottom >= 16,
              `${id}: authority source panel lost bottom padding`);
            fail(list.scrollWidth <= list.clientWidth + tolerance,
              `${id}: authority source text overflowed the panel`);
          }
        }

        const historyPanel = document.querySelector(".study-history-controls");
        const historyRect = historyPanel.getBoundingClientRect();
        const historyStyle = getComputedStyle(historyPanel);
        const historyLeft = historyRect.left + numeric(historyStyle.paddingLeft);
        const historyRight = historyRect.right - numeric(historyStyle.paddingRight);
        const input = document.querySelector("#history-import");
        const inputRect = input.getBoundingClientRect();
        const labelRect = input.closest("label").getBoundingClientRect();
        fail(inputRect.height >= 44, "History restore input lost its 44px touch target");
        fail(within(inputRect, historyLeft, historyRight), "History restore input escaped panel padding");
        fail(within(inputRect, labelRect.left, labelRect.right), "History restore input escaped label width");

        const controls = document.querySelector(".controls");
        const controlsRect = controls.getBoundingClientRect();
        const controlsStyle = getComputedStyle(controls);
        const controlsLeft = controlsRect.left + numeric(controlsStyle.paddingLeft);
        const controlsRight = controlsRect.right - numeric(controlsStyle.paddingRight);
        for (const field of controls.querySelectorAll(".search-field, .select-field, .filter-group")) {
          const rect = field.getBoundingClientRect();
          fail(within(rect, controlsLeft, controlsRight), `${field.className}: filter escaped panel padding`);
          for (const control of field.querySelectorAll("input, select, button")) {
            const controlRect = control.getBoundingClientRect();
            fail(within(controlRect, rect.left, rect.right), `${control.id || control.textContent}: filter control escaped field width`);
          }
        }
        return {
          checkedChildren, checkedSources,
          historyInputHeight: inputRect.height,
          failures: failures.slice(0, 20),
          failureCount: failures.length,
        };
      });
      check(layout.checkedSources > 0, `${width}px: authority sources were not exercised`);
      check(layout.failureCount === 0, `${width}px: spacing violations: ${JSON.stringify(layout)}`);
      await noDocumentOverflow("with all answers open");

      await view.locator("#toggle-visible-answers").click();
      check(await view.locator("[data-answer-disclosure][open]").count() === 0,
        `${width}px: bulk close did not close all answers`);
      await noDocumentOverflow("after bulk close");
      check(errors.length === 0, `${width}px: browser errors: ${errors.join("; ")}`);
      results.push({ viewport: width, cards: inventory, ...layout });
    } finally {
      await context.close();
    }
  }
  return { passed: true, viewports: results };
}
