import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

const SETTLE_MS = 12_000;

function flowIdFrom(page: Page): string {
  const m = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!m) throw new Error(`no flow id in ${page.url()}`);
  return m[1];
}

async function tokenOf(page: Page, flowId: string): Promise<string> {
  const r = await page.request.get(`/api/v1/flows/${flowId}/version-state`);
  return (await r.json()).version_token;
}

test("running a flow must not take the writer's turn from other tabs", async ({
  page,
}) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);

  const before = await tokenOf(page, flowId);
  await page
    .getByTestId("button_run_chat output")
    .click({ timeout: 20_000 })
    .catch((e) => console.log("D4 run click failed:", e.message));
  await page.waitForTimeout(SETTLE_MS * 2);
  const after = await tokenOf(page, flowId);
  console.log(
    "D4 token before run:",
    before,
    "after run:",
    after,
    "rotated:",
    before !== after,
  );
  expect(after, "a run alone must not rotate the version token").toBe(before);
});

test("rapid editing never leaves the server behind the canvas", async ({
  page,
}) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);

  const node = page.locator(".react-flow__node").first();
  await expect(node).toBeVisible();

  // 25 seconds of continuous dragging: longer than the debounce and its maxWait.
  const box = await node.boundingBox();
  if (!box) throw new Error("no box");
  const started = Date.now();
  let x = box.x + box.width / 2;
  let y = box.y + 10;
  while (Date.now() - started < 25_000) {
    await page.mouse.move(x, y);
    await page.mouse.down();
    y = y + 12 > box.y + 260 ? box.y + 10 : y + 12;
    await page.mouse.move(x, y, { steps: 3 });
    await page.mouse.up();
    await page.waitForTimeout(400);
  }
  await page.waitForTimeout(SETTLE_MS * 2);

  const canvas = await page.evaluate(() => {
    const st = (window as any).__lfFlowStore;
    return null;
  });
  const server = await (
    await page.request.get(`/api/v1/flows/${flowId}`)
  ).json();
  const positions = (server.data?.nodes ?? []).map(
    (n: any) =>
      `${n.id}:${Math.round(n.position.x)},${Math.round(n.position.y)}`,
  );
  console.log("D5 server positions after the burst:", positions.join(" | "));

  // The canvas position of the node we dragged, straight from the DOM transform.
  const domPos = await node.evaluate((el) => {
    const t = (el as HTMLElement).style.transform;
    return t;
  });
  console.log("D5 canvas transform:", domPos);
  const nodeId = await node.getAttribute("data-id");
  const serverNode = (server.data?.nodes ?? []).find(
    (n: any) => n.id === nodeId,
  );
  const m = domPos.match(/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/);
  if (m && serverNode) {
    const dx = Math.abs(Number(m[1]) - serverNode.position.x);
    const dy = Math.abs(Number(m[2]) - serverNode.position.y);
    console.log("D5 canvas vs server delta:", dx, dy);
    expect(
      dx + dy,
      "the last edit of a burst must reach the server",
    ).toBeLessThan(2);
  }
});
