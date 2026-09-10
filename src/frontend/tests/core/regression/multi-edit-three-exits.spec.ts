import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

/**
 * Two people on one flow, and the three ways the second one gets out.
 *
 * The dialog offers update, duplicate and discard. Only the first two were ever
 * covered; discard is the exit the kickoff asked for and nothing tested.
 */

const SETTLE_MS = 12_000;
const CONFLICT_WINDOW_MS = 25_000;

function flowIdFrom(page: Page): string {
  const m = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!m) throw new Error(`no flow id in ${page.url()}`);
  return m[1];
}

/** The other person saves a change of their own. */
async function otherPersonEdits(page: Page, flowId: string): Promise<number> {
  const flow = await (await page.request.get(`/api/v1/flows/${flowId}`)).json();
  const nodes = flow.data?.nodes ?? [];
  const target = nodes[nodes.length - 1];
  target.position = {
    x: (target.position?.x ?? 0) + 220,
    y: (target.position?.y ?? 0) + 150,
  };
  const write = await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: { ...flow.data, nodes } },
  });
  expect(write.status()).toBe(200);
  return target.position.y as number;
}

async function dragFirstNode(page: Page) {
  const node = page.locator(".react-flow__node").first();
  const box = await node.boundingBox();
  if (!box) throw new Error("no bounding box");
  await page.mouse.move(box.x + box.width / 2, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + 150, { steps: 12 });
  await page.mouse.up();
}

async function raiseConflict(page: Page): Promise<string> {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);
  await otherPersonEdits(page, flowId);
  await dragFirstNode(page);
  await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
    timeout: CONFLICT_WINDOW_MS,
  });
  return flowId;
}

test("the banner offers the two direct exits and the dialog names all three", async ({
  page,
}) => {
  test.setTimeout(3 * 60 * 1000);
  await raiseConflict(page);

  const banner = page.getByTestId("flow-conflict-banner");
  await expect(banner.getByText(/newer version/i)).toBeVisible();
  // It used to offer duplicating only, long after a second exit shipped.
  await expect(
    banner.getByTestId("flow-conflict-load-latest-button"),
  ).toBeVisible();
  await expect(banner.getByTestId("flow-conflict-review-button")).toBeVisible();

  await page.getByTestId("flow-conflict-review-button").click();
  const modal = page.getByTestId("duplicate-flow-modal");
  await expect(modal).toBeVisible();
  await expect(modal.getByText(/review version changes/i).first()).toBeVisible();
  await expect(modal.getByTestId("confirm-overwrite-flow")).toHaveText(
    /update current flow/i,
  );
  await expect(modal.getByTestId("confirm-duplicate-flow")).toBeVisible();
});

test("discarding asks first, then takes the other person's version", async ({
  page,
}) => {
  test.setTimeout(3 * 60 * 1000);
  const flowId = await raiseConflict(page);
  const theirGraph = await (
    await page.request.get(`/api/v1/flows/${flowId}`)
  ).json();

  // Still asked twice: the work becomes recoverable, not unimportant.
  await page.getByTestId("flow-conflict-load-latest-button").click();
  await expect(page.getByTestId("load-latest-dialog")).toBeVisible();
  const writes: number[] = [];
  page.on("response", (r) => {
    if (r.request().method() === "PATCH" && r.url().includes("/flows/"))
      writes.push(r.status());
  });
  await page.getByTestId("load-latest-confirm-button").click();

  // The conflict is over, the person stays on the flow, and nothing was written.
  await expect(page.getByTestId("flow-conflict-banner")).toBeHidden({
    timeout: CONFLICT_WINDOW_MS,
  });
  await expect(page.getByTestId("duplicate-flow-modal")).toBeHidden();
  expect(page.url()).toContain(flowId);

  await page.waitForTimeout(SETTLE_MS);
  const after = await (
    await page.request.get(`/api/v1/flows/${flowId}`)
  ).json();
  expect(
    after.version_token,
    "discarding must not write anything to the flow",
  ).toBe(theirGraph.version_token);
  expect(
    writes.filter((s) => s === 409),
    "no refused save may follow",
  ).toHaveLength(0);

  // The whole point of the exit: the abandoned canvas is recoverable.
  const versions = await (
    await page.request.get(`/api/v1/flows/${flowId}/versions/`)
  ).json();
  const entries = versions.entries ?? versions;
  const archived = entries.find((v: { description?: string }) =>
    (v.description ?? "").toLowerCase().includes("discard"),
  );
  expect(archived, "discarding archives the canvas it threw away").toBeTruthy();

  const archivedGraph = await (
    await page.request.get(`/api/v1/flows/${flowId}/versions/${archived.id}`)
  ).json();
  expect(
    JSON.stringify(archivedGraph.data),
    "the archived version is the discarded work, not the version that won",
  ).not.toBe(JSON.stringify(theirGraph.data));

  // The stranded draft went with the decision, so a reload does not offer it back.
  const drafts = await page.evaluate(() =>
    Object.keys(localStorage).filter((k) => k.startsWith("lf_draft_")),
  );
  expect(drafts, "the discarded work is not kept").toEqual([]);
});

test("after discarding, editing saves normally again", async ({ page }) => {
  test.setTimeout(3 * 60 * 1000);
  const flowId = await raiseConflict(page);

  await page.getByTestId("flow-conflict-load-latest-button").click();
  await page.getByTestId("load-latest-confirm-button").click();
  await expect(page.getByTestId("flow-conflict-banner")).toBeHidden({
    timeout: CONFLICT_WINDOW_MS,
  });
  await page.waitForTimeout(SETTLE_MS);

  const writes: number[] = [];
  page.on("response", (r) => {
    if (r.request().method() === "PATCH" && r.url().includes("/flows/"))
      writes.push(r.status());
  });
  await dragFirstNode(page);
  await page.waitForTimeout(SETTLE_MS);

  expect(writes.length, "the flow must be saveable again").toBeGreaterThan(0);
  expect(
    writes.filter((s) => s === 409),
    "and not refused",
  ).toHaveLength(0);
  await expect(page.getByTestId("flow-conflict-banner")).toBeHidden();
});
