import type { Route } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import type { LangflowPage } from "../../utils/types";

const MESSAGE_COUNT = 150;

const label = (position: number) => `#${String(position).padStart(3, "0")}`;

// Newest first: #001 is the newest message, #150 the oldest.
const history = Array.from({ length: MESSAGE_COUNT }, (_, index) => ({
  id: `history-${label(index + 1).slice(1)}`,
  flow_id: "history-flow",
  session_id: "history-session",
  timestamp: new Date(
    Date.UTC(2026, 8, 1, 12, 0) - index * 60_000,
  ).toISOString(),
  text: label(index + 1),
  sender: "User",
  sender_name: "history",
  files: [],
  edit: false,
  error: false,
  properties: {},
  category: "message",
  content_blocks: [],
}));

const rowOf = (text: string) => history.find((row) => row.text === text)!;

/**
 * Serve GET /monitor/messages the way the real endpoint pages it: newest first,
 * by `offset` or below a `before_timestamp`/`before_id` position, over rows that
 * can change between requests.
 * Deleting a row here stands in for a delete from another tab or API client,
 * which the page is never told about.
 */
async function mockMessageHistory(page: LangflowPage) {
  const deleted = new Set<string>();
  const requests: URLSearchParams[] = [];

  await page.route(
    /\/api\/v1\/monitor\/messages(\?.*)?$/,
    async (route: Route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const params = new URL(route.request().url()).searchParams;
      requests.push(params);
      const live = history.filter((row) => !deleted.has(row.id));
      const limit = Number(params.get("limit") ?? 100);
      const offset = Number(params.get("offset") ?? 0);
      const beforeId = params.get("before_id");
      const beforeTime = new Date(
        params.get("before_timestamp") ?? "",
      ).getTime();
      const below = beforeId
        ? live.filter((row) => {
            const time = new Date(row.timestamp).getTime();
            return (
              time < beforeTime || (time === beforeTime && row.id < beforeId)
            );
          })
        : live.slice(offset);
      const window = below.slice(0, limit);
      await route.fulfill({
        json: params.get("order") === "ASC" ? window.reverse() : window,
      });
    },
  );

  return {
    deleteElsewhere: (text: string) => deleted.add(rowOf(text).id),
    lastRequest: () => requests[requests.length - 1],
  };
}

// The grid renders only the rows in view, so scroll it to read every row.
function readGridTexts(page: LangflowPage) {
  return page.evaluate(async () => {
    const viewport = document.querySelector(".ag-body-viewport");
    const texts = new Set<string>();
    if (!viewport) return [];
    for (let top = 0; top <= viewport.scrollHeight; top += 200) {
      viewport.scrollTop = top;
      await new Promise((resolve) => requestAnimationFrame(resolve));
      for (const cell of document.querySelectorAll('.ag-cell[col-id="text"]')) {
        texts.add((cell as HTMLElement).innerText.trim());
      }
    }
    viewport.scrollTop = 0;
    return [...texts];
  });
}

test(
  "loading older messages does not skip one after a message is deleted elsewhere",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const server = await mockMessageHistory(page);
    await awaitBootstrapTest(page, { skipModal: true });
    await page.goto("/settings/messages");

    const loadOlder = page.getByTestId("load-older-messages");
    await expect(loadOlder).toBeVisible({ timeout: TIMEOUTS.standard });
    // The first page is #001-#100; the grid lists it oldest first.
    await expect(
      page.locator('.ag-cell[col-id="text"]').filter({ hasText: /^#100$/ }),
    ).toBeVisible();

    // An offset-based next page would now start one row too far back and skip #101.
    server.deleteElsewhere("#050");
    await loadOlder.click();

    await expect
      .poll(async () => (await readGridTexts(page)).includes("#101"), {
        timeout: TIMEOUTS.medium,
      })
      .toBe(true);
    expect(server.lastRequest().get("before_id")).toBe(rowOf("#100").id);
    expect(server.lastRequest().get("before_timestamp")).toBe(
      rowOf("#100").timestamp,
    );
    expect(server.lastRequest().has("offset")).toBe(false);
  },
);
