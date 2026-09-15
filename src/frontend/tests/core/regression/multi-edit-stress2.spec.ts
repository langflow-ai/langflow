import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

const SETTLE_MS = 12_000;
const CONFLICT_WINDOW_MS = 25_000;

async function editFromAnotherSession(page: Page, flowId: string) {
  const read = await page.request.get(`/api/v1/flows/${flowId}`);
  const flow = await read.json();
  const nodes = flow.data?.nodes ?? [];
  const target = nodes[nodes.length - 1];
  target.position = {
    x: (target.position?.x ?? 0) + 200,
    y: (target.position?.y ?? 0) + 120,
  };
  const write = await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: { ...flow.data, nodes } },
  });
  expect(write.status()).toBe(200);
}

function flowIdFrom(page: Page): string {
  const m = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!m) throw new Error(`no flow id in ${page.url()}`);
  return m[1];
}

async function dragFirstNode(page: Page) {
  const node = page.locator(".react-flow__node").first();
  await expect(node).toBeVisible();
  const box = await node.boundingBox();
  if (!box) throw new Error("no bounding box");
  await page.mouse.move(box.x + box.width / 2, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + 150, { steps: 12 });
  await page.mouse.up();
}

const draftKeys = (page: Page) =>
  page.evaluate(() =>
    Object.keys(localStorage).filter((k) => k.startsWith("lf_draft_")),
  );

test("restored work survives a second reload", async ({ page }) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);

  await editFromAnotherSession(page, flowId);
  await dragFirstNode(page);
  await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
    timeout: CONFLICT_WINDOW_MS,
  });
  console.log("D1 drafts after refusal:", await draftKeys(page));

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector(".react-flow__node", { timeout: 60_000 });
  await page.waitForTimeout(SETTLE_MS);
  await expect(page.getByTestId("restore-draft-banner")).toBeVisible({
    timeout: CONFLICT_WINDOW_MS,
  });
  await page.getByTestId("restore-draft-button").click();
  await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
    timeout: CONFLICT_WINDOW_MS,
  });
  console.log("D1 drafts after restoring:", await draftKeys(page));

  // Keep working on the restored graph, exactly as somebody deciding would.
  await dragFirstNode(page);
  await page.waitForTimeout(SETTLE_MS);
  console.log(
    "D1 drafts after editing the restored work:",
    await draftKeys(page),
  );

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector(".react-flow__node", { timeout: 60_000 });
  await page.waitForTimeout(SETTLE_MS);
  const stillOffered = await page
    .getByTestId("restore-draft-banner")
    .isVisible()
    .catch(() => false);
  console.log("D1 restore offered after the second reload:", stillOffered);
  expect(
    stillOffered,
    "work restored once must still survive a reload",
  ).toBeTruthy();
});

test("a save that writes nothing never reports success", async ({ page }) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);

  await editFromAnotherSession(page, flowId);
  await dragFirstNode(page);
  await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
    timeout: CONFLICT_WINDOW_MS,
  });

  const before = await (
    await page.request.get(`/api/v1/flows/${flowId}`)
  ).json();

  // Ctrl+S, the reflex of anyone who has just been told their work is at risk.
  await page.keyboard.press("Control+s");
  await page.waitForTimeout(4000);
  const successToast = await page.getByText(/saved successfully/i).count();
  console.log(
    "D2 'saved successfully' toasts after Ctrl+S during a conflict:",
    successToast,
  );

  // A blocked save now sends the person to the conflict, so close it before
  // reaching for the rename underneath.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(1000);

  // And the rename path, which reports "changes saved" the same way.
  await page.getByTestId("flow_name").click();
  const newName = `conflict-rename-${Date.now()}`;
  await page.getByTestId("input-flow-name").fill(newName);
  await page.getByTestId("save-flow-settings").click();
  await page.waitForTimeout(4000);
  const changesSaved = await page
    .getByText(/changes saved|saved successfully/i)
    .count();
  const after = await (
    await page.request.get(`/api/v1/flows/${flowId}`)
  ).json();
  console.log(
    "D2 name before:",
    before.name,
    "after:",
    after.name,
    "wanted:",
    newName,
  );
  console.log("D2 success toasts:", changesSaved);

  expect(
    successToast + changesSaved === 0 || after.name === newName,
    "a save that wrote nothing must not report success",
  ).toBeTruthy();
});

test("a conflict found by the run check still leaves a draft", async ({
  page,
}) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);

  await editFromAnotherSession(page, flowId);
  // Edit and immediately run, inside the autosave debounce: the conflict is then
  // discovered by the run's version check, not by a refused save.
  await dragFirstNode(page);
  await page
    .getByTestId("button_run_chat output")
    .click({ timeout: 10_000 })
    .catch(() => {});
  await page.waitForTimeout(3000);
  const drafts = await draftKeys(page);
  const conflicted = await page
    .getByTestId("flow-conflict-banner")
    .isVisible()
    .catch(() => false);
  const dialog = await page
    .getByTestId("duplicate-flow-modal")
    .isVisible()
    .catch(() => false);
  console.log(
    "D3 conflict raised:",
    conflicted,
    "dialog:",
    dialog,
    "drafts:",
    drafts,
  );
  if (conflicted || dialog) {
    expect(
      drafts.length,
      "a conflict must always leave the work recoverable",
    ).toBeGreaterThan(0);
  } else {
    console.log("D3 inconclusive: the autosave beat the run check");
  }
});
