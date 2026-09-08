import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

/**
 * Two people, one flow, both editing without pause.
 *
 * Every other test here stages a single collision. This one runs the thing the
 * feature is named after: sustained simultaneous editing, long enough for the
 * autosave debounce and its ceiling to fire many times over on both sides.
 */

// Chrome throttles timers in a tab that is not in front, and the autosave is a
// timer. Without this both tabs sat on a single debounce for the whole run and
// the storm measured nothing at all.
test.use({
  launchOptions: {
    args: [
      "--disable-background-timer-throttling",
      "--disable-backgrounding-occluded-windows",
      "--disable-renderer-backgrounding",
    ],
  },
});

const SETTLE_MS = 12_000;
const STORM_MS = 90_000;

type Traffic = {
  patches: number;
  refused: number;
  serverErrors: { status: number; url: string }[];
};

function watch(page: Page, label: string): Traffic {
  const traffic: Traffic = { patches: 0, refused: 0, serverErrors: [] };
  page.on("response", (r) => {
    if (!/\/api\/v\d\/flows\//i.test(r.url())) return;
    if (r.request().method() === "PATCH") {
      traffic.patches += 1;
      if (r.status() === 409) traffic.refused += 1;
    }
    if (r.status() >= 500) {
      traffic.serverErrors.push({ status: r.status(), url: r.url() });
      console.log(`${label} server error ${r.status()} ${r.url()}`);
    }
  });
  return traffic;
}

function flowIdFrom(page: Page): string {
  const m = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!m) throw new Error(`no flow id in ${page.url()}`);
  return m[1];
}

/** Drags a node around the canvas the way a person fiddling with a layout does. */
async function keepEditing(
  page: Page,
  until: number,
  seed: number,
): Promise<number> {
  const node = page.locator(".react-flow__node").nth(seed % 2);
  let drags = 0;
  while (Date.now() < until) {
    // Re-read the box every time. Holding the first one and tracking the cursor
    // by hand drifted off the node within two moves, and every drag after that
    // panned the canvas instead of editing anything — a storm that wrote nothing.
    const box = await node.boundingBox();
    if (!box) break;
    const fromX = box.x + box.width / 2;
    const fromY = box.y + 10;
    const dx = ((drags * 23 + seed * 13) % 90) - 45;
    const dy = ((drags * 17 + seed * 31) % 90) - 45;
    await page.mouse.move(fromX, fromY);
    await page.mouse.down();
    await page.mouse.move(fromX + dx, fromY + dy, { steps: 4 });
    await page.mouse.up();
    drags += 1;
    await page.waitForTimeout(500);
  }
  return drags;
}

test("two people editing the same flow without pause", async ({
  page,
  context,
}) => {
  test.setTimeout(6 * 60 * 1000);

  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);
  const url = page.url();

  const tabB = await context.newPage();
  await tabB.goto(url);
  await tabB.waitForSelector(".react-flow__node", { timeout: 60_000 });
  await adjustScreenView(tabB);
  await tabB.waitForTimeout(SETTLE_MS);

  const a = watch(page, "A");
  const b = watch(tabB, "B");

  const until = Date.now() + STORM_MS;
  const [dragsA, dragsB] = await Promise.all([
    keepEditing(page, until, 1),
    keepEditing(tabB, until, 2),
  ]);
  console.log("drags A:", dragsA, "drags B:", dragsB);
  await page.waitForTimeout(SETTLE_MS);
  await tabB.waitForTimeout(SETTLE_MS);

  const bannerA = await page
    .getByTestId("flow-conflict-banner")
    .isVisible()
    .catch(() => false);
  const bannerB = await tabB
    .getByTestId("flow-conflict-banner")
    .isVisible()
    .catch(() => false);

  console.log(
    "A patches:", a.patches, "refused:", a.refused, "banner:", bannerA,
    "| B patches:", b.patches, "refused:", b.refused, "banner:", bannerB,
  );

  // 1. Nothing may 5xx, however hard the two of them push.
  expect(a.serverErrors, "A saw a server error").toHaveLength(0);
  expect(b.serverErrors, "B saw a server error").toHaveLength(0);

  // The storm has to have been a storm: a debounce of 5s with a 15s ceiling over
  // 90s of unbroken editing is many writes, not one.
  expect(
    a.patches + b.patches,
    "the run must actually have exercised the autosave",
  ).toBeGreaterThan(6);

  // 2. Someone kept the flow, and whoever lost it was told rather than dropped.
  expect(bannerA || bannerB, "a collision must be surfaced somewhere").toBe(
    true,
  );
  const loser = bannerA ? a : b;
  const loserPage = bannerA ? page : tabB;
  const winner = bannerA ? b : a;
  const winnerPage = bannerA ? tabB : page;
  expect(
    loser.refused,
    "the loser is refused once, then left alone",
  ).toBe(1);
  expect(bannerA && bannerB, "both tabs cannot lose to each other").toBe(false);

  // 3. The loser's work is recoverable, not stranded in memory.
  const drafts = await loserPage.evaluate(() =>
    Object.keys(localStorage).filter((k) => k.startsWith("lf_draft_")),
  );
  expect(drafts.length, "the refused work must be on disk").toBeGreaterThan(0);

  // 4. The winner is still saving, and the server holds their graph.
  const patchesBefore = winner.patches;
  await keepEditing(winnerPage, Date.now() + 12_000, 3);
  await winnerPage.waitForTimeout(SETTLE_MS);
  expect(
    winner.patches,
    "the winner must still be saving after the storm",
  ).toBeGreaterThan(patchesBefore);
  expect(winner.refused, "the winner is still never refused").toBe(0);

  // 5. And the loser has stopped writing entirely.
  const loserPatchesBefore = loser.patches;
  await keepEditing(loserPage, Date.now() + 12_000, 4);
  await loserPage.waitForTimeout(SETTLE_MS);
  expect(
    loser.patches,
    "a conflicted tab must not keep hammering the server",
  ).toBe(loserPatchesBefore);

  // 6. The server's graph matches the winner's canvas, node for node.
  const server = await page.request.get(`/api/v1/flows/${flowId}`);
  const saved = (await server.json()).data;
  const canvasCount = await winnerPage.locator(".react-flow__node").count();
  expect(saved.nodes.length, "the server holds the winner's graph").toBe(
    canvasCount,
  );

  // 7. The loser's exit still works after all that.
  await loserPage.getByTestId("flow-conflict-review-button").click();
  await expect(loserPage.getByTestId("duplicate-flow-modal")).toBeVisible();
  await loserPage.getByTestId("confirm-duplicate-flow").click();
  await expect
    .poll(() => loserPage.url(), { timeout: 30_000 })
    .not.toContain(flowId);
  console.log("loser duplicated into", loserPage.url());

  // 8. And the copy is a normal, saveable flow.
  const copyTraffic = watch(loserPage, "copy");
  await loserPage.waitForSelector(".react-flow__node", { timeout: 60_000 });
  await loserPage.waitForTimeout(SETTLE_MS);
  await keepEditing(loserPage, Date.now() + 12_000, 5);
  await loserPage.waitForTimeout(SETTLE_MS);
  console.log(
    "copy patches:", copyTraffic.patches, "refused:", copyTraffic.refused,
  );
  expect(copyTraffic.patches, "the copy must save").toBeGreaterThan(0);
  expect(copyTraffic.refused, "the copy must not conflict").toBe(0);

  await tabB.close();
});
