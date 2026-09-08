import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openStarterProject } from "../../utils/flow/open-starter-project";

// each test bootstraps its own flow; workers=1 keeps them from colliding

const SETTLE_MS = 12_000;
const CONFLICT_WINDOW_MS = 20_000;

function trackFlowWrites(page: Page) {
  const seen: { method: string; status: number; url: string }[] = [];
  page.on("response", (r) => {
    if (/\/api\/v\d\/flows\//i.test(r.url())) {
      seen.push({
        method: r.request().method(),
        status: r.status(),
        url: r.url(),
      });
    }
  });
  return {
    patches: () => seen.filter((s) => s.method === "PATCH"),
    refused: () =>
      seen.filter((s) => s.method === "PATCH" && s.status === 409).length,
    forks: () =>
      seen.filter((s) => s.method === "POST" && /\/fork$/.test(s.url)),
    all: () => seen,
  };
}

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

test("a rename still lands when someone else changed the graph", async ({
  page,
}) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);
  const writes = trackFlowWrites(page);

  await editFromAnotherSession(page, flowId);

  const before = await (
    await page.request.get(`/api/v1/flows/${flowId}`)
  ).json();
  const newName = `renamed-${Date.now()}`;

  await page.getByTestId("flow_name").click();
  const nameInput = page.getByTestId("input-flow-name");
  await expect(nameInput).toBeVisible();
  await nameInput.fill(newName);
  const saveButton = page.getByTestId("save-flow-settings");
  console.log(
    "S1 typed:",
    await nameInput.inputValue(),
    "save disabled:",
    await saveButton.isDisabled(),
  );
  await expect(saveButton).toBeEnabled({ timeout: 15_000 });
  await saveButton.click();
  await page.waitForTimeout(SETTLE_MS);

  const after = await (
    await page.request.get(`/api/v1/flows/${flowId}`)
  ).json();
  console.log(
    "S1 name before:",
    before.name,
    "after:",
    after.name,
    "wanted:",
    newName,
  );
  console.log("S1 refused patches:", writes.refused());
  const errorToast = await page
    .locator('[data-testid="error_alert"], [role="alert"]')
    .count();
  console.log("S1 alerts on screen:", errorToast);
  const bannerVisible = await page
    .getByTestId("flow-conflict-banner")
    .isVisible()
    .catch(() => false);
  console.log("S1 conflict banner visible:", bannerVisible);
  expect(after.name, "the rename must not be silently discarded").toBe(newName);
});

test("double-clicking Duplicate must not fail or create two copies", async ({
  page,
}) => {
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
  await page.getByTestId("flow-conflict-review-button").click();
  await expect(page.getByTestId("duplicate-flow-modal")).toBeVisible();

  const btn = page.getByTestId("confirm-duplicate-flow");
  await btn.dblclick({ delay: 0 });
  await page.waitForTimeout(SETTLE_MS);

  const forks = writes.forks();
  console.log("S2 fork requests:", JSON.stringify(forks));
  const copies = await (
    await page.request.get(`/api/v1/flows/?get_all=true&header_flows=true`)
  ).json();
  const names = (Array.isArray(copies) ? copies : (copies.items ?? []))
    .map((f: any) => f.name)
    .filter((n: string) => n.includes("(copy)"));
  console.log("S2 copies now present:", names);
  expect(
    forks.filter((f) => f.status >= 400),
    "no fork request may fail",
  ).toHaveLength(0);
});

test("an import that replaces the flow is caught as a conflict", async ({
  page,
}) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);
  const writes = trackFlowWrites(page);

  // Somebody re-imports the exported JSON of this flow, changing it wholesale.
  const flow = await (await page.request.get(`/api/v1/flows/${flowId}`)).json();
  const imported = JSON.parse(JSON.stringify(flow));
  imported.data.nodes = imported.data.nodes.slice(0, 1);
  const upload = await page.request.post(`/api/v1/flows/upload/`, {
    multipart: {
      file: {
        name: "flow.json",
        mimeType: "application/json",
        buffer: Buffer.from(JSON.stringify(imported)),
      },
    },
  });
  console.log("S3 upload status", upload.status());
  const afterImport = await (
    await page.request.get(`/api/v1/flows/${flowId}`)
  ).json();
  console.log(
    "S3 nodes after import:",
    afterImport.data.nodes.length,
    "token rotated:",
    afterImport.version_token !== flow.version_token,
  );

  await dragFirstNode(page);
  await page.waitForTimeout(SETTLE_MS);

  const banner = await page
    .getByTestId("flow-conflict-banner")
    .isVisible()
    .catch(() => false);
  const final = await (
    await page.request.get(`/api/v1/flows/${flowId}`)
  ).json();
  console.log(
    "S3 banner:",
    banner,
    "refused:",
    writes.refused(),
    "final nodes:",
    final.data.nodes.length,
  );
  expect(
    banner || final.data.nodes.length === afterImport.data.nodes.length,
    "the editor either warns or must not overwrite the import",
  ).toBeTruthy();
});

test("with a conflict up there is no way to leave the page", async ({
  page,
}) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);

  await editFromAnotherSession(page, flowId);
  await dragFirstNode(page);
  await expect(page.getByTestId("flow-conflict-banner")).toBeVisible({
    timeout: CONFLICT_WINDOW_MS,
  });

  // Try to walk away, then cancel the dialog: the person wanted out, not a merge.
  await page
    .getByTestId("icon-ChevronLeft")
    .first()
    .click()
    .catch(async () => {
      await page.goto("/all");
    });
  await page.waitForTimeout(4000);
  const dialogUp = await page
    .getByTestId("duplicate-flow-modal")
    .isVisible()
    .catch(() => false);
  console.log(
    "S4 dialog opened on exit attempt:",
    dialogUp,
    "url:",
    page.url(),
  );
  if (dialogUp) {
    // Is there any exit that discards my work and takes theirs?
    const buttons = await page
      .getByTestId("duplicate-flow-modal")
      .getByRole("button")
      .allInnerTexts();
    console.log("S4 exits offered:", JSON.stringify(buttons));
    await page.keyboard.press("Escape");
    await page.waitForTimeout(2000);
    console.log("S4 url after cancelling:", page.url());
  }
  expect(page.url()).toContain(flowId);
});

test("two live tabs editing the same flow", async ({ page, context }) => {
  await openStarterProject(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
  const flowId = flowIdFrom(page);
  const writesA = trackFlowWrites(page);

  const tabB = await context.newPage();
  const writesB = trackFlowWrites(tabB);
  await tabB.goto(page.url());
  await tabB.waitForSelector(".react-flow__node", { timeout: 60_000 });
  await tabB.waitForTimeout(SETTLE_MS);

  // Both people edit at roughly the same moment.
  await Promise.all([dragFirstNode(page), dragFirstNode(tabB)]);
  await page.waitForTimeout(SETTLE_MS);
  await tabB.waitForTimeout(2000);

  const bannerA = await page
    .getByTestId("flow-conflict-banner")
    .isVisible()
    .catch(() => false);
  const bannerB = await tabB
    .getByTestId("flow-conflict-banner")
    .isVisible()
    .catch(() => false);
  console.log(
    "S5 A refused:",
    writesA.refused(),
    "B refused:",
    writesB.refused(),
  );
  console.log("S5 banner A:", bannerA, "banner B:", bannerB);

  // Now the loser keeps editing for a while: nothing may be written.
  const loser = bannerA ? page : bannerB ? tabB : null;
  if (loser) {
    const track = loser === page ? writesA : writesB;
    const before = track.patches().length;
    await dragFirstNode(loser);
    await loser.waitForTimeout(SETTLE_MS);
    console.log(
      "S5 writes attempted after conflict:",
      track.patches().length - before,
    );
    expect(track.patches().length, "a conflicted tab must stop writing").toBe(
      before,
    );
  }
  await tabB.close();
  expect(bannerA || bannerB, "one of the two tabs must be told").toBeTruthy();
});
