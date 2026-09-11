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

function flowIdFrom(page: Page): string {
  const m = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!m) throw new Error("no flow id");
  return m[1];
}

test("conflict dialog footer layout", async ({ page }) => {
  test.setTimeout(3 * 60 * 1000);
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);

  // Someone else changes several components, so both lists have content.
  const flow = await (await page.request.get(`/api/v1/flows/${flowId}`)).json();
  const nodes = flow.data.nodes.map((n: ServerNode, i: number) => ({
    ...n,
    position: {
      x: (n.position?.x ?? 0) + 60 * (i + 1),
      y: (n.position?.y ?? 0) + 40,
    },
  }));
  await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: { ...flow.data, nodes } },
  });

  const node = page.locator(".react-flow__node").first();
  const box = await node.boundingBox();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + 10);
  await page.mouse.down();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + 150, { steps: 12 });
  await page.mouse.up();

  await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
    timeout: 25_000,
  });
  await page.getByTestId("flow-conflict-review-button").click();
  const modal = page.getByTestId("duplicate-flow-modal");
  await expect(modal).toBeVisible();
  await page.waitForTimeout(1500);
  await modal.screenshot({ path: "test-results/conflict-dialog.png" });

  // The remaining actions must sit on one row: measure their vertical centres.
  const tops = await modal.evaluate(() => {
    const ids = ["confirm-duplicate-flow", "confirm-overwrite-flow"];
    const els = ids
      .map((id) => document.querySelector(`[data-testid="${id}"]`))
      .filter(Boolean) as HTMLElement[];
    const cancel = Array.from(document.querySelectorAll("button")).find(
      (b) => b.textContent?.trim().toLowerCase() === "cancel",
    );
    if (cancel) els.unshift(cancel as HTMLElement);
    return els.map((e) => Math.round(e.getBoundingClientRect().top));
  });
  console.log("button tops:", JSON.stringify(tops));
  expect(new Set(tops).size, "all actions on a single row").toBe(1);

  // And the confirmation step, which now lives off the banner.
  await page.keyboard.press("Escape");
  await expect(modal).toBeHidden();
  await page.getByTestId("flow-conflict-review-button").click();
  await page.getByTestId("dialog-load-latest-button").click();
  await page.waitForTimeout(800);
  const confirm = page.getByTestId("load-latest-confirm-button");
  console.log(
    "confirm button text:",
    JSON.stringify(await confirm.textContent()),
    "| text-transform:",
    await confirm.evaluate((el) => getComputedStyle(el).textTransform),
  );
  await page
    .getByTestId("load-latest-confirm")
    .screenshot({ path: "test-results/conflict-dialog-discard.png" });
});
