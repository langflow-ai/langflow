import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

/** The shape of a node as the flows API returns it. */
type ServerNode = {
  id: string;
  position?: { x?: number; y?: number };
  data?: { node?: { template?: Record<string, { value?: unknown }> } };
};

const SETTLE_MS = 12_000;
const CONFLICT_WINDOW_MS = 25_000;

function flowIdFrom(page: Page): string {
  const m = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!m) throw new Error(`no flow id in ${page.url()}`);
  return m[1];
}

/** Moves a node AND edits a field on it, from another session: one component, two changes. */
async function editOneComponentTwice(page: Page, flowId: string) {
  const read = await page.request.get(`/api/v1/flows/${flowId}`);
  const flow = await read.json();
  const nodes = flow.data?.nodes ?? [];
  const target = nodes.find((n: ServerNode) =>
    Object.keys(n.data?.node?.template ?? {}).some(
      (f) => typeof n.data.node.template[f]?.value === "string",
    ),
  );
  if (!target) throw new Error("no node with a text field");

  target.position = {
    x: (target.position?.x ?? 0) + 220,
    y: (target.position?.y ?? 0) + 140,
  };
  const field = Object.keys(target.data.node.template).find(
    (f) => typeof target.data.node.template[f]?.value === "string",
  )!;
  target.data.node.template[field].value =
    `changed by the other tab ${Date.now()}`;

  const write = await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: { ...flow.data, nodes } },
  });
  expect(write.status()).toBe(200);
  return target.id as string;
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

test("two changes to one component are one row with one checkbox", async ({
  page,
}) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);

  const touchedId = await editOneComponentTwice(page, flowId);
  await dragFirstNode(page);
  await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
    timeout: CONFLICT_WINDOW_MS,
  });

  await page.getByTestId("flow-conflict-review-button").click();
  const modal = page.getByTestId("duplicate-flow-modal");
  await expect(modal).toBeVisible();

  // The component that was moved and edited must appear once, not twice.
  const row = page.getByTestId(`conflict-change-theirs-node:${touchedId}`);
  await expect(row).toHaveCount(1);
  const boxes = row.getByRole("checkbox");
  await expect(boxes, "one component, one checkbox").toHaveCount(1);

  // And both of its changes are stated inside that single row.
  const lines = await row.locator("li").count();
  console.log("changes listed inside the row:", lines);
  expect(lines, "both changes must still be spelled out").toBeGreaterThan(1);

  // One tick takes the whole component, and the counter counts components.
  await boxes.click();
  await expect(boxes, "the row is taken as a whole").toBeChecked();
  await expect(modal.getByText(/1 of \d+ selected/i)).toBeVisible();

  // My own version of that component is then shown as replaced, not dropped quietly.
  const mine = page.getByTestId(`conflict-change-mine-node:${touchedId}`);
  await expect(mine.getByRole("checkbox")).not.toBeChecked();
  await expect(mine.getByText(/replaced by/i)).toBeVisible();
});
