import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

/**
 * What the autosave debounce costs and buys at each interval.
 *
 * The interval is a product decision about database load, but it is also the
 * clock the whole multi-edit feature runs on: nothing is written, and so no
 * conflict is discovered, until the debounce fires. These tests measure both
 * halves against a real server so the number is chosen from evidence.
 *
 * The interval is forced through the config response rather than the server's
 * environment, so one run can compare several values on one backend.
 */

test.describe.configure({ mode: "serial" });

const SETTLE_MS = 12_000;
const CONFLICT_WINDOW_MS = 30_000;

/** Gaps sit between 2s and 10s, so the two intervals must disagree. */
const NUDGE_GAP_MS = 3_500;
const NUDGE_COUNT = 8;

async function forceInterval(page: Page, ms: number): Promise<void> {
  await page.route("**/api/v1/config", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: { ...body, auto_saving_interval: ms },
    });
  });
}

function trackFlowWrites(page: Page): {
  total: () => number;
  stamps: () => number[];
} {
  const stamps: number[] = [];
  page.on("response", (response) => {
    if (
      response.request().method() === "PATCH" &&
      /\/api\/v\d\/flows\/[0-9a-f-]{36}/i.test(response.url())
    ) {
      stamps.push(Date.now());
    }
  });
  return { total: () => stamps.length, stamps: () => [...stamps] };
}

function flowIdFrom(page: Page): string {
  const match = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!match) throw new Error(`no flow id in ${page.url()}`);
  return match[1];
}

/** One small drag: the cheapest edit that still marks the flow dirty. */
async function nudgeNode(page: Page, offset: number): Promise<void> {
  const node = page.locator(".react-flow__node").first();
  const box = await node.boundingBox();
  if (!box) throw new Error("the node has no bounding box");
  await page.mouse.move(box.x + box.width / 2, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + 10 + offset, {
    steps: 6,
  });
  await page.mouse.up();
}

async function editFromAnotherSession(
  page: Page,
  flowId: string,
): Promise<void> {
  const read = await page.request.get(`/api/v1/flows/${flowId}`);
  const flow = await read.json();
  const nodes = flow.data?.nodes ?? [];
  const target = nodes[nodes.length - 1];
  target.position = {
    x: (target.position?.x ?? 0) + 240,
    y: (target.position?.y ?? 0) + 160,
  };
  const write = await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: { ...flow.data, nodes } },
  });
  expect(write.status(), "the other session's save must succeed").toBe(200);
}

async function measureBurst(page: Page, interval: number): Promise<number> {
  await forceInterval(page, interval);
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);

  const writes = trackFlowWrites(page);
  for (let i = 0; i < NUDGE_COUNT; i++) {
    await nudgeNode(page, i % 2 === 0 ? 60 : -60);
    await page.waitForTimeout(NUDGE_GAP_MS);
  }
  // Let the final trailing save land before counting.
  await page.waitForTimeout(interval + 4_000);
  return writes.total();
}

test(
  "a longer debounce turns a burst of edits into fewer writes",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const atTwo = await measureBurst(page, 2_000);
    const atTen = await measureBurst(page, 10_000);

    // eslint-disable-next-line no-console
    console.log(`writes for ${NUDGE_COUNT} edits: 2s=${atTwo}, 10s=${atTen}`);

    expect(
      atTwo,
      "edits spaced above the interval each cost a write",
    ).toBeGreaterThan(1);
    expect(
      atTen,
      "the same edits spaced below the interval must collapse into fewer writes",
    ).toBeLessThan(atTwo);
  },
);

test(
  "a continuous burst cannot defer its save past the ceiling",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    // The shipping configuration: a 5s debounce with a 15s ceiling. Without the
    // ceiling this same burst produced no write at all until the editing stopped.
    await forceInterval(page, 5_000);
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const writes = trackFlowWrites(page);
    const start = Date.now();
    // Gaps below the debounce, so nothing here would ever trail out on its own.
    for (let i = 0; i < 9; i++) {
      await nudgeNode(page, i % 2 === 0 ? 50 : -50);
      await page.waitForTimeout(3_000);
    }

    expect(
      writes.total(),
      "the ceiling must persist the burst while it is still going",
    ).toBeGreaterThan(0);

    const unsavedFor = writes.stamps()[0] - start;
    // eslint-disable-next-line no-console
    console.log(
      `first write landed ${Math.round(unsavedFor / 1000)}s into the burst`,
    );
    expect(
      unsavedFor,
      "work may not sit unsaved past the ceiling plus one interval",
    ).toBeLessThan(25_000);
  },
);

test(
  "the conflict is still caught at ten seconds, only later",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await forceInterval(page, 10_000);
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const flowId = flowIdFrom(page);
    await editFromAnotherSession(page, flowId);

    const edited = Date.now();
    await nudgeNode(page, 80);

    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });
    const detected = Date.now() - edited;
    // eslint-disable-next-line no-console
    console.log(
      `conflict surfaced ${Math.round(detected / 1000)}s after the edit`,
    );

    expect(
      detected,
      "detection cannot beat the debounce: the save is what discovers the conflict",
    ).toBeGreaterThan(9_000);
  },
);

test(
  "leaving with a debounce still pending is guarded, not silently lost",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await forceInterval(page, 10_000);
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    await nudgeNode(page, 70);
    // Navigate while the save is still owed, the moment a longer interval makes
    // more likely. The unsaved-changes guard is what stands between the person
    // and losing the whole burst.
    await page.waitForTimeout(1_000);
    await page.getByTestId("icon-ChevronLeft").first().click();

    await expect(
      page.getByText(/unsaved changes/i).first(),
      "an owed save must not be dropped without telling the person",
    ).toBeVisible({ timeout: 15_000 });
  },
);
