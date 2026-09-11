import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

/**
 * A save that would overwrite somebody else is refused, and the person is offered
 * a duplicate that carries their own work.
 *
 * The unit tests cover the diff engine and the conflict store. Only this covers
 * the seam between them and the server: the token has to survive the round trip,
 * the refusal has to reach the banner, and autosave has to actually stop.
 */

// Each test bootstraps its own flow, and two of those at once make the shared
// creation step return 400.
test.describe.configure({ mode: "serial" });

const SETTLE_MS = 12_000;
const CONFLICT_WINDOW_MS = 20_000;

function trackFlowWrites(page: Page): {
  total: () => number;
  refused: () => number;
} {
  let total = 0;
  let refused = 0;
  page.on("response", (response) => {
    if (
      response.request().method() === "PATCH" &&
      /\/api\/v\d\/flows\/[0-9a-f-]{36}/i.test(response.url())
    ) {
      total += 1;
      if (response.status() === 409) refused += 1;
    }
  });
  return { total: () => total, refused: () => refused };
}

/** Writes the flow from outside this tab, the way a second person would. */
async function editFromAnotherSession(
  page: Page,
  flowId: string,
): Promise<void> {
  // Through the browser context's request API, not the page: the app installs a
  // global fetch interceptor, so an in-page fetch is this session, not another.
  const read = await page.request.get(`/api/v1/flows/${flowId}`);
  expect(read.status(), "the other session must be able to read").toBe(200);
  const flow = await read.json();

  const nodes = flow.data?.nodes ?? [];
  expect(nodes.length, "the starter flow must have nodes").toBeGreaterThan(0);
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

function flowIdFrom(page: Page): string {
  const match = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!match) throw new Error(`no flow id in ${page.url()}`);
  return match[1];
}

async function dragFirstNode(page: Page): Promise<void> {
  const node = page.locator(".react-flow__node").first();
  await expect(node).toBeVisible();
  const box = await node.boundingBox();
  if (!box) throw new Error("the node has no bounding box");
  await page.mouse.move(box.x + box.width / 2, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + 170, { steps: 14 });
  await page.mouse.up();
}

test(
  "a refused save raises the banner and stops autosaving",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const flowId = flowIdFrom(page);
    const writes = trackFlowWrites(page);

    await editFromAnotherSession(page, flowId);
    await dragFirstNode(page);

    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });
    await expect(page.getByTestId("flow-conflict-frame")).toBeAttached();
    expect(writes.refused(), "the stale save must be refused").toBeGreaterThan(
      0,
    );

    await page.runA11yScan("flow-conflict-banner");

    // Autosave must not keep hammering a write that can never succeed.
    const afterConflict = writes.total();
    await dragFirstNode(page);
    await page.waitForTimeout(SETTLE_MS);

    expect(
      writes.total(),
      "no further save may be attempted once the flow is in conflict",
    ).toBe(afterConflict);
  },
);

test(
  "duplicating carries my work and leaves the original alone",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const flowId = flowIdFrom(page);
    await editFromAnotherSession(page, flowId);
    await dragFirstNode(page);

    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });

    await page.getByTestId("flow-conflict-review-button").click();
    const modal = page.getByTestId("duplicate-flow-modal");
    await expect(modal).toBeVisible();

    await page.runA11yScan("duplicate-flow-modal");

    // My own work is stated.
    await expect(
      modal.getByRole("heading", { name: /your changes/i }),
    ).toBeVisible();

    await page.getByTestId("confirm-duplicate-flow").click();
    await expect
      .poll(() => page.url(), { timeout: CONFLICT_WINDOW_MS })
      .not.toContain(flowId);

    await expect(page.getByTestId("flow-conflict-banner")).toBeHidden();

    // The whole promise of the exit: the other person's version survived intact.
    const originalResponse = await page.request.get(`/api/v1/flows/${flowId}`);
    const original = await originalResponse.json();

    expect(
      original.data?.nodes?.length ?? 0,
      "the original must still hold a graph",
    ).toBeGreaterThan(0);
  },
);

test(
  "running without editing is never treated as a conflict",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const flowId = flowIdFrom(page);
    // Somebody else moves the flow on while this tab sits there, untouched.
    await editFromAnotherSession(page, flowId);

    const writes = trackFlowWrites(page);
    await page.getByTestId("button_run_chat output").click();
    await page.waitForTimeout(SETTLE_MS);

    // Running is not editing. Someone who changed nothing has nothing to
    // duplicate, and a dialog offering no changes on either side is not an exit.
    expect(
      writes.refused(),
      "a run with no edits must not have a save refused",
    ).toBe(0);
    await expect(page.getByTestId("flow-conflict-banner")).toBeHidden();
    await expect(page.getByTestId("duplicate-flow-modal")).toBeHidden();
  },
);

test(
  "work restored after a reload is still recognised as stale",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const flowId = flowIdFrom(page);
    await editFromAnotherSession(page, flowId);
    await dragFirstNode(page);
    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForSelector(".react-flow__node", { timeout: 60_000 });
    await page.waitForTimeout(SETTLE_MS);

    await expect(page.getByTestId("restore-draft-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });
    await page.getByTestId("restore-draft-button").click();

    // The restored graph was built on a version the flow has moved past. Nothing
    // else would notice: the baseline reloaded with the page is already current,
    // so without saying so a later run would adopt the server's version straight
    // over the work that was just handed back.
    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });
  },
);

test(
  "the source flow still detects conflicts after duplicating and going back",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const flowId = flowIdFrom(page);
    await editFromAnotherSession(page, flowId);
    await dragFirstNode(page);
    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });

    await page.getByTestId("flow-conflict-review-button").click();
    await expect(page.getByTestId("duplicate-flow-modal")).toBeVisible();
    await page.getByTestId("confirm-duplicate-flow").click();
    await expect
      .poll(() => page.url(), { timeout: CONFLICT_WINDOW_MS })
      .not.toContain(flowId);
    // The url changes before the copy has finished mounting, and going back while
    // it is still settling lands on the copy again rather than on the source.
    await page.waitForTimeout(3000);

    // The browser Back button, not a fresh load: this is a history pop inside the
    // app, and it is the path people actually take back to the flow they left.
    await page.goBack({ waitUntil: "domcontentloaded" });
    await page.waitForSelector(".react-flow__node", { timeout: 60_000 });
    await page.waitForTimeout(SETTLE_MS);
    expect(page.url(), "Back must return to the source flow").toContain(flowId);

    const writes = trackFlowWrites(page);
    await editFromAnotherSession(page, flowId);
    await dragFirstNode(page);

    // Duplicating marks the source abandoned so its queued save stops retrying.
    // Reopening must lift that: while it did not, the flow came back silently
    // unsaveable — edits were dropped, and no conflict could ever be raised.
    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });
    expect(
      writes.refused(),
      "the returned-to flow must still send its precondition",
    ).toBeGreaterThan(0);
  },
);

test(
  "overwriting keeps my merge and files their version in history",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const flowId = flowIdFrom(page);
    await editFromAnotherSession(page, flowId);
    await dragFirstNode(page);

    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });
    await page.getByTestId("flow-conflict-review-button").click();
    await expect(page.getByTestId("duplicate-flow-modal")).toBeVisible();

    await page.getByTestId("confirm-overwrite-flow").click();

    // Overwriting stays on the flow, unlike duplicating, which navigates away.
    await expect(page.getByTestId("flow-conflict-banner")).toBeHidden({
      timeout: CONFLICT_WINDOW_MS,
    });
    expect(page.url()).toContain(flowId);

    // The version that was replaced has to be recoverable, or overwriting would
    // be exactly the silent data loss this whole feature exists to prevent.
    const versions = await page.request.get(
      `/api/v1/flows/${flowId}/versions/`,
    );
    const entries = (await versions.json()).entries ?? [];
    expect(entries.length, "the replaced version must be archived").toBe(1);
    expect(
      entries[0].username,
      "history has to name who authored the archived version",
    ).toBeTruthy();

    // Saving works again straight away: overwriting hands back a current token.
    const writesAfter = trackFlowWrites(page);
    await dragFirstNode(page);
    await page.waitForTimeout(SETTLE_MS);
    expect(
      writesAfter.refused(),
      "no save may be refused once the overwrite has resolved the conflict",
    ).toBe(0);
    expect(writesAfter.total()).toBeGreaterThan(0);
  },
);

test(
  "overwriting with their change selected keeps it on the canvas",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const flowId = flowIdFrom(page);
    await editFromAnotherSession(page, flowId);
    await dragFirstNode(page);

    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });
    await page.getByTestId("flow-conflict-review-button").click();

    const modal = page.getByTestId("duplicate-flow-modal");
    await expect(modal).toBeVisible();
    const theirChange = modal.getByRole("checkbox", { checked: false }).first();
    await expect(theirChange).toBeVisible();
    await theirChange.click();

    await page.getByTestId("confirm-overwrite-flow").click();
    await expect(page.getByTestId("flow-conflict-banner")).toBeHidden({
      timeout: CONFLICT_WINDOW_MS,
    });

    // Adopting only the baseline left the canvas on the author's own graph, so
    // the change taken from them vanished from the screen and the next autosave
    // wrote that loss straight back over the merge.
    const writes = trackFlowWrites(page);
    await page.waitForTimeout(SETTLE_MS);
    const server = await page.request.get(`/api/v1/flows/${flowId}`);
    const saved = (await server.json()).data;

    const canvasNodeCount = await page.locator(".react-flow__node").count();
    expect(
      saved.nodes.length,
      "the server must still hold the merge, not the author's graph alone",
    ).toBe(canvasNodeCount);
    expect(writes.refused(), "the resolved flow must keep saving cleanly").toBe(
      0,
    );
  },
);

test(
  "a save landing while the dialog is open refreshes it instead of dead-ending",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openStarterProject(page, "Basic Prompting");
    await adjustScreenView(page);
    await page.waitForTimeout(SETTLE_MS);

    const flowId = flowIdFrom(page);
    await editFromAnotherSession(page, flowId);
    await dragFirstNode(page);

    await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });
    await page.getByTestId("flow-conflict-review-button").click();
    await expect(page.getByTestId("duplicate-flow-modal")).toBeVisible();

    // A third save lands while the dialog sits open on a now-outdated comparison.
    await editFromAnotherSession(page, flowId);
    await page.getByTestId("confirm-overwrite-flow").click();

    // Refused, correctly — but the dialog has to come back rebuilt on the version
    // that won, or the person can only keep retrying the same refused write.
    await expect(page.getByTestId("duplicate-flow-modal")).toBeVisible({
      timeout: CONFLICT_WINDOW_MS,
    });

    // The notice is the only deterministic signal that the rebuild finished:
    // the button re-enables a tick before the refreshed token reaches state, so
    // waiting on it alone reproduces the very race this test is about.
    await expect(
      page.getByText(/saved again while you were choosing/i).first(),
    ).toBeVisible({ timeout: CONFLICT_WINDOW_MS });

    // And it now succeeds against the version that won.
    await page.getByTestId("confirm-overwrite-flow").click();
    await expect(page.getByTestId("flow-conflict-banner")).toBeHidden({
      timeout: CONFLICT_WINDOW_MS,
    });
    expect(page.url()).toContain(flowId);
  },
);
