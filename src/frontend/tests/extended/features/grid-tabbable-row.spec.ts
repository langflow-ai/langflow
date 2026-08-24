import type { Route } from "@playwright/test";
import { expect, type LangflowPage, test } from "../../fixtures";
import { TIMEOUTS } from "../../utils/constants/timeouts";

/**
 * WCAG 2.1.1 Keyboard regression test for the shared AG-Grid wrapper
 * (components/core/parameterRenderComponent/components/tableComponent).
 *
 * The grid exposes exactly one tabbable `role="row"` — the roving tab stop that
 * lets a keyboard user enter it (IBM `aria_child_tabbable`). Row virtualization
 * recycles the row holding that tab stop out of the DOM as soon as the user
 * scrolls past it. Before the `viewportChanged` / `modelUpdated` wiring the tab
 * stop was assigned once on first render and never reassigned, so scrolling a
 * long grid left it with zero tabbable rows and no way back in — it did not
 * even recover on scrolling to the top again.
 *
 * The messages table is mocked with enough rows to force recycling; the grids
 * that pass today (API keys, global variables) only do so because their handful
 * of rows never scroll far enough to recycle one.
 */

const MOCK_FLOW_ID = "fcfc747e-0b93-4ff5-a9e1-3788c14a849b";
const MOCK_MESSAGE_COUNT = 250;

function buildMessages(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    flow_id: MOCK_FLOW_ID,
    timestamp: `2026-08-19 16:${String(index % 60).padStart(2, "0")}:00.000000 UTC`,
    sender: index % 2 ? "Machine" : "User",
    sender_name: index % 2 ? "Language Model" : "User",
    session_id: MOCK_FLOW_ID,
    context_id: "",
    text: `Seeded message ${index}`,
    files: "[]",
    edit: false,
    duration: null,
    properties: {
      text_color: null,
      background_color: null,
      edited: false,
      source: { id: null, display_name: null, source: null },
      icon: null,
      allow_markdown: false,
      positive_feedback: null,
      state: "complete",
      targets: [],
      usage: null,
      build_duration: null,
    },
    category: "message",
    content_blocks: [],
    session_metadata: { graph_run_id: MOCK_FLOW_ID },
  }));
}

/** Rows the grid currently exposes as keyboard tab stops. Must never be empty. */
async function getTabbableRowIndexes(page: LangflowPage): Promise<string[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll('[role="row"]')]
      .filter((row) => {
        const tabindex = row.getAttribute("tabindex");
        return tabindex !== null && tabindex !== "-1";
      })
      .map((row) => row.getAttribute("row-index") ?? "header"),
  );
}

async function getViewportMetrics(page: LangflowPage) {
  return page.evaluate(() => {
    const viewport = document.querySelector(".ag-body-viewport");
    if (!viewport) throw new Error("grid body viewport not found");
    return {
      scrollTop: viewport.scrollTop,
      scrollHeight: viewport.scrollHeight,
      clientHeight: viewport.clientHeight,
    };
  });
}

async function scrollGridTo(page: LangflowPage, scrollTop: number) {
  await page.evaluate((top) => {
    const viewport = document.querySelector(".ag-body-viewport");
    if (!viewport) throw new Error("grid body viewport not found");
    viewport.scrollTop = top;
  }, scrollTop);
  // The tab stop is reassigned on the grid's viewportChanged event and applied
  // on the next animation frame, so wait for the grid to settle before reading.
  await page.waitForTimeout(400);
}

test(
  "messages grid keeps a tabbable row while the rows around it are virtualized away",
  { tag: ["@release", "@workspace"] },
  async ({ page }, testInfo) => {
    await page.route("**/api/v1/monitor/messages*", async (route: Route) => {
      if (route.request().method() !== "GET") return route.continue();
      await route.fulfill({ json: buildMessages(MOCK_MESSAGE_COUNT) });
    });

    await page.goto("/settings/messages");
    await page
      .locator('.ag-center-cols-container [role="row"]')
      .first()
      .waitFor({ timeout: TIMEOUTS.standard });

    const metrics = await getViewportMetrics(page);
    // Guard the premise: without overflow no row is ever recycled and the test
    // would pass against the unfixed code.
    expect(
      metrics.scrollHeight,
      "mocked grid must overflow its viewport, otherwise no row is virtualized away",
    ).toBeGreaterThan(metrics.clientHeight * 2);

    expect(
      await getTabbableRowIndexes(page),
      "grid must expose exactly one tab stop on load",
    ).toHaveLength(1);

    const maxScroll = metrics.scrollHeight - metrics.clientHeight;
    const steps = [
      ...Array.from({ length: 5 }, (_, i) =>
        Math.round((maxScroll * (i + 1)) / 5),
      ),
      maxScroll,
      0,
    ];

    for (const scrollTop of steps) {
      await scrollGridTo(page, scrollTop);
      expect(
        await getTabbableRowIndexes(page),
        `grid lost its keyboard tab stop at scrollTop=${scrollTop}`,
      ).toHaveLength(1);
    }

    await testInfo.attach("messages-grid-scrolled-back-to-top", {
      body: await page.screenshot(),
      contentType: "image/png",
    });
  },
);

test(
  "messages grid stays keyboard-enterable and arrow-navigable after scrolling",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await page.route("**/api/v1/monitor/messages*", async (route: Route) => {
      if (route.request().method() !== "GET") return route.continue();
      await route.fulfill({ json: buildMessages(MOCK_MESSAGE_COUNT) });
    });

    await page.goto("/settings/messages");
    await page
      .locator('.ag-center-cols-container [role="row"]')
      .first()
      .waitFor({ timeout: TIMEOUTS.standard });

    const { scrollHeight, clientHeight } = await getViewportMetrics(page);
    await scrollGridTo(page, scrollHeight - clientHeight);

    expect(
      await getTabbableRowIndexes(page),
      "grid lost its keyboard tab stop after scrolling to the bottom",
    ).toHaveLength(1);

    // Tab in from the page chrome. AG Grid's tab guards intercept the entry and
    // hand focus to a header cell rather than to the roving row itself, so the
    // assertion is "focus ends up inside the grid", not "focus lands on the row".
    await page.evaluate(() => document.body.focus());
    let enteredAfter = -1;
    for (let press = 0; press < 40; press++) {
      await page.keyboard.press("Tab");
      const insideGrid = await page.evaluate(() =>
        Boolean(document.activeElement?.closest(".ag-root-wrapper")),
      );
      if (insideGrid) {
        enteredAfter = press;
        break;
      }
    }
    expect(
      enteredAfter,
      "could not reach the grid with the Tab key after scrolling",
    ).toBeGreaterThanOrEqual(0);

    // Arrow keys still drive AG Grid's own cell navigation once focus is inside.
    await page.keyboard.press("ArrowDown");
    await expect(page.locator(".ag-cell-focus")).toHaveCount(1);
    const firstCell = await page
      .locator(".ag-cell-focus")
      .getAttribute("col-id");

    await page.keyboard.press("ArrowDown");
    await expect(page.locator(".ag-cell-focus")).toHaveCount(1);
    expect(
      await page.locator(".ag-cell-focus").getAttribute("col-id"),
      "ArrowDown should stay in the same column while moving down rows",
    ).toBe(firstCell);
  },
);
