import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";

/**
 * The trail, end to end: a person edits the canvas, and the record says who they
 * were and what they changed.
 *
 * Runs against a backend started with LANGFLOW_FLOW_AUDIT_ENABLED=true. Without
 * it the read route answers 404 by design, and the spec skips rather than
 * pretending to have tested anything.
 */

const SETTLE_MS = 12_000;

/** Opens a real starter graph on the canvas without going through the welcome flow. */
async function openFlowFromStarter(page: Page, name: string): Promise<string> {
  // Land on the app first: the request context borrows the session the page
  // establishes, and an unauthenticated call answers an error object, not a list.
  await page.goto("/");
  await page.waitForSelector("body", { timeout: 30_000 });
  await expect
    .poll(async () => (await page.request.get("/api/v1/flows/?get_all=true&header_flows=true")).status(), {
      timeout: 60_000,
    })
    .toBe(200);

  const response = await page.request.get("/api/v1/starter-projects/");
  const body = await response.json();
  // The route has answered as a bare list and as a paginated envelope; take either.
  const starters: any[] = Array.isArray(body) ? body : (body.items ?? body.starter_projects ?? []);
  const template = starters.find((s: any) => (s.name ?? s.data?.name) === name);
  if (!template) throw new Error(`no starter project named ${name}`);

  const created = await page.request.post("/api/v1/flows/", {
    data: {
      name: `audit-e2e-${Date.now()}`,
      description: "",
      data: template.data,
    },
  });
  expect(created.status(), await created.text()).toBe(201);
  const flow = await created.json();

  await page.goto(`/flow/${flow.id}`);
  await page.waitForSelector(".react-flow__node", { timeout: 60_000 });
  return flow.id as string;
}

function flowIdFrom(page: Page): string {
  const m = page.url().match(/\/flow\/([0-9a-f-]{36})/i);
  if (!m) throw new Error(`no flow id in ${page.url()}`);
  return m[1];
}

async function trail(page: Page, flowId: string) {
  const response = await page.request.get(`/api/v1/flows/${flowId}/audit/`);
  if (response.status() === 404) test.skip(true, "audit trail not enabled on this backend");
  expect(response.status()).toBe(200);
  return (await response.json()).entries as Array<Record<string, any>>;
}

/** Deletes a node from the canvas: an edit the editor performs on a key press. */
async function deleteFirstNode(page: Page) {
  const node = page.locator(".react-flow__node").first();
  const box = await node.boundingBox();
  if (!box) throw new Error("no bounding box");
  await node.click({ position: { x: 10, y: Math.min(8, box.height / 2) } });
  await page.waitForTimeout(500);
  await page.keyboard.press("Delete");
}

test("editing the canvas records who changed the flow and what they changed", async ({
  page,
}) => {
  test.setTimeout(3 * 60 * 1000);

  const flowId = await openFlowFromStarter(page, "Basic Prompting");
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);

  expect(await trail(page, flowId), "a flow nobody edited has no trail").toEqual([]);

  // A drag is the editor's own write path: the store marks the flow edited, the
  // autosave sends it, and the server describes what it did.
  const writes: string[] = [];
  page.on("response", (r) => {
    if (r.request().method() === "PATCH" && r.url().includes("/flows/")) writes.push(`${r.status()}`);
  });
  const nodesBefore = await page.locator(".react-flow__node").count();
  await deleteFirstNode(page);
  await expect
    .poll(() => page.locator(".react-flow__node").count(), { timeout: 30_000 })
    .toBe(nodesBefore - 1);
  await page.waitForTimeout(SETTLE_MS);

  const entries = await trail(page, flowId);
  const server = await (await page.request.get(`/api/v1/flows/${flowId}`)).json();
  console.log(
    "patches:", JSON.stringify(writes),
    "nodes on server:", server.data.nodes.length,
    "entries:", JSON.stringify(entries).slice(0, 400),
  );

  expect(entries, "one editing session, one entry").toHaveLength(1);
  const [entry] = entries;
  expect(entry.username, "the entry names who did it").toBeTruthy();
  expect(entry.source).toBe("editor");
  const described = entry.changes.flatMap((group: any) =>
    group.changes.map((change: any) => ({ label: group.label, ...change })),
  );
  expect(
    described.some((c: any) => c.kind === "node_removed"),
    "the deletion is recorded",
  ).toBe(true);

  // A field edited from another session lands in the same trail, with its values.
  const flow = await (await page.request.get(`/api/v1/flows/${flowId}`)).json();
  const nodes = flow.data.nodes;
  const target = nodes.find((n: any) =>
    Object.values(n.data?.node?.template ?? {}).some(
      (f: any) => typeof f?.value === "string" && f?.password !== true,
    ),
  );
  const fieldName = Object.keys(target.data.node.template).find(
    (k) =>
      typeof target.data.node.template[k]?.value === "string" &&
      target.data.node.template[k]?.password !== true,
  )!;
  const before = target.data.node.template[fieldName].value;
  target.data.node.template[fieldName].value = "audited value";
  const write = await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: { ...flow.data, nodes } },
  });
  expect(write.status()).toBe(200);

  const after = await trail(page, flowId);
  const fieldChange = after
    .flatMap((e: any) => e.changes)
    .flatMap((g: any) => g.changes)
    .find((c: any) => c.field === fieldName);
  console.log("field change recorded:", JSON.stringify(fieldChange));
  expect(fieldChange, "the field change is described").toBeTruthy();
  expect(fieldChange.after).toBe("audited value");
  if (before && before.length <= 60 && !before.includes("\n")) {
    expect(fieldChange.before).toBe(before);
  }
});

test("a secret changed on a flow never reaches the trail", async ({ page }) => {
  test.setTimeout(3 * 60 * 1000);

  await page.goto("/");
  await expect
    .poll(
      async () => (await page.request.get("/api/v1/flows/?get_all=true&header_flows=true")).status(),
      { timeout: 60_000 },
    )
    .toBe(200);

  const secret = `sk-live-${Date.now()}`;
  const withSecret = (value: string) => ({
    nodes: [
      {
        id: "n0",
        position: { x: 0, y: 0 },
        data: {
          id: "n0",
          node: {
            display_name: "OpenAI",
            template: { api_key: { display_name: "API Key", value, password: true } },
          },
        },
      },
    ],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  });

  const created = await page.request.post("/api/v1/flows/", {
    data: { name: `audit-secret-${Date.now()}`, description: "", data: withSecret("sk-live-original") },
  });
  expect(created.status()).toBe(201);
  const flowId = (await created.json()).id;

  const write = await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: withSecret(secret) },
  });
  expect(write.status()).toBe(200);

  const entries = await trail(page, flowId);
  console.log("secret entry:", JSON.stringify(entries).slice(0, 400));
  expect(JSON.stringify(entries), "the secret is nowhere in the trail").not.toContain(secret);
  expect(JSON.stringify(entries), "nor the value it replaced").not.toContain("sk-live-original");

  const secretChange = entries
    .flatMap((e: any) => e.changes)
    .flatMap((g: any) => g.changes)
    .find((c: any) => c.secret);
  expect(secretChange, "but the field is recorded as touched").toBeTruthy();
});
