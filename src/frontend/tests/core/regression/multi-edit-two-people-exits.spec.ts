import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

/**
 * Two people on one flow, each of the three exits, and what the other one sees.
 *
 * Everything else stages the collision from one side. This drives both tabs and
 * checks the exit from the point of view of the person who did not take it.
 */

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
const CONFLICT_WINDOW_MS = 25_000;

function flowIdFrom(page: Page): string {
  const m = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!m) throw new Error(`no flow id in ${page.url()}`);
  return m[1];
}

async function moveANode(page: Page, presses = 0) {
  const node = page.locator(".react-flow__node").first();
  const box = await node.boundingBox();
  if (!box) throw new Error("no bounding box");
  await page.mouse.move(box.x + box.width / 2, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + 140 + presses * 20, {
    steps: 12,
  });
  await page.mouse.up();
}

/** Alice opens the flow, Bob opens the same one beside her. */
async function twoPeopleOnOneFlow(page: Page, context) {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);

  const bob = await context.newPage();
  await bob.goto(page.url());
  await bob.waitForSelector(".react-flow__node", { timeout: 60_000 });
  await adjustScreenView(bob);
  await bob.waitForTimeout(SETTLE_MS);

  // Alice saves first; Bob is now holding a version the flow has moved past.
  await moveANode(page);
  await page.waitForTimeout(SETTLE_MS);

  await moveANode(bob, 2);
  await expect(bob.getByTestId("flow-conflict-banner")).toBeVisible({
    timeout: CONFLICT_WINDOW_MS,
  });
  return { flowId, alice: page, bob };
}

test("Bob takes the latest: Alice's version stands and nobody is refused", async ({
  page,
  context,
}) => {
  test.setTimeout(5 * 60 * 1000);
  const { flowId, alice, bob } = await twoPeopleOnOneFlow(page, context);
  const aliceVersion = await (
    await alice.request.get(`/api/v1/flows/${flowId}`)
  ).json();

  await bob.getByTestId("flow-conflict-review-button").click();

  await bob.getByTestId("dialog-load-latest-button").click();
  await bob.getByTestId("load-latest-confirm-button").click();
  await expect(bob.getByTestId("flow-conflict-banner")).toBeHidden({
    timeout: CONFLICT_WINDOW_MS,
  });

  // Alice is untouched and still saving cleanly.
  const aliceWrites: number[] = [];
  alice.on("response", (r) => {
    if (r.request().method() === "PATCH" && r.url().includes("/flows/"))
      aliceWrites.push(r.status());
  });
  await moveANode(alice, 3);
  await alice.waitForTimeout(SETTLE_MS);

  const server = await (
    await alice.request.get(`/api/v1/flows/${flowId}`)
  ).json();
  console.log(
    "take-latest: alice writes",
    JSON.stringify(aliceWrites),
    "| bob banner gone, token moved only by alice:",
    server.version_token !== aliceVersion.version_token,
  );
  expect(
    aliceWrites.filter((s) => s === 409),
    "Alice is never refused",
  ).toHaveLength(0);
  await expect(alice.getByTestId("flow-conflict-banner")).toBeHidden();
  await bob.close();
});

test("Bob updates the flow: Alice is told her version is now out of date", async ({
  page,
  context,
}) => {
  test.setTimeout(5 * 60 * 1000);
  const { flowId, alice, bob } = await twoPeopleOnOneFlow(page, context);

  await bob.getByTestId("flow-conflict-review-button").click();
  await bob.getByTestId("confirm-overwrite-flow").click();
  await expect(bob.getByTestId("flow-conflict-banner")).toBeHidden({
    timeout: CONFLICT_WINDOW_MS,
  });

  // The version Bob replaced is recoverable, attributed to whoever wrote it.
  const versions = await (
    await bob.request.get(`/api/v1/flows/${flowId}/versions/`)
  ).json();
  expect(
    versions.entries?.length,
    "the replaced version is archived",
  ).toBeGreaterThan(0);
  expect(versions.entries[0].username, "and it names its author").toBeTruthy();

  // Alice now holds a stale version, and learns it the moment she edits.
  await moveANode(alice, 4);
  await expect(alice.getByTestId("flow-conflict-banner")).toBeVisible({
    timeout: CONFLICT_WINDOW_MS,
  });
  await expect(
    alice.getByTestId("flow-conflict-banner").getByText(/newer version/i),
  ).toBeVisible();
  console.log(
    "update-flow: bob saved, alice correctly told her version is stale",
  );
  await bob.close();
});

test("Bob duplicates: he keeps his work and Alice's flow is untouched", async ({
  page,
  context,
}) => {
  test.setTimeout(5 * 60 * 1000);
  const { flowId, alice, bob } = await twoPeopleOnOneFlow(page, context);
  const before = await (
    await alice.request.get(`/api/v1/flows/${flowId}`)
  ).json();

  await bob.getByTestId("flow-conflict-review-button").click();
  await bob.getByTestId("confirm-duplicate-flow").click();
  await expect
    .poll(() => bob.url(), { timeout: CONFLICT_WINDOW_MS })
    .not.toContain(flowId);
  await bob.waitForTimeout(SETTLE_MS);

  const after = await (
    await alice.request.get(`/api/v1/flows/${flowId}`)
  ).json();
  expect(after.version_token, "Alice's flow is untouched").toBe(
    before.version_token,
  );

  // And Alice keeps working with no conflict of her own.
  const aliceWrites: number[] = [];
  alice.on("response", (r) => {
    if (r.request().method() === "PATCH" && r.url().includes("/flows/"))
      aliceWrites.push(r.status());
  });
  await moveANode(alice, 5);
  await alice.waitForTimeout(SETTLE_MS);
  console.log(
    "duplicate: alice writes",
    JSON.stringify(aliceWrites),
    "bob at",
    bob.url(),
  );
  expect(aliceWrites.filter((s) => s === 409)).toHaveLength(0);
  await expect(alice.getByTestId("flow-conflict-banner")).toBeHidden();
  await bob.close();
});
