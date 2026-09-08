import type { Browser, Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";

/**
 * Two, three and four people on one flow, with the audit trail switched on.
 *
 * The point is the interaction between the two features: the conflict machinery
 * decides who may write, and the trail has to end up describing exactly the
 * writes that actually happened — no more, no fewer, and never a secret.
 *
 * Runs against a backend started with LANGFLOW_FLOW_AUDIT_ENABLED=true.
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

type Person = { name: string; page: Page; writes: number[] };

async function openFlowFor(page: Page, flowId: string) {
  await page.goto(`/flow/${flowId}`);
  await page.waitForSelector(".react-flow__node", { timeout: 60_000 });
  await adjustScreenView(page);
  await page.waitForTimeout(SETTLE_MS);
}

/** Creates the flow once from a starter, then seats `count` people on it. */
async function seatPeople(
  page: Page,
  browser: Browser,
  count: number,
): Promise<{ flowId: string; people: Person[]; contexts: any[] }> {
  await page.goto("/");
  await expect
    .poll(
      async () =>
        (await page.request.get("/api/v1/flows/?get_all=true&header_flows=true")).status(),
      { timeout: 60_000 },
    )
    .toBe(200);

  const body = await (await page.request.get("/api/v1/starter-projects/")).json();
  const starters: any[] = Array.isArray(body) ? body : (body.items ?? []);
  const template = starters.find((s: any) => (s.name ?? s.data?.name) === "Basic Prompting");
  const created = await page.request.post("/api/v1/flows/", {
    data: { name: `crowd-${Date.now()}`, description: "", data: template.data },
  });
  expect(created.status()).toBe(201);
  const flowId = (await created.json()).id as string;

  const people: Person[] = [];
  const contexts: any[] = [];
  for (let i = 0; i < count; i++) {
    const seat = i === 0 ? page : await (await browser.newContext()).newPage();
    if (i > 0) contexts.push(seat.context());
    const person: Person = { name: `p${i + 1}`, page: seat, writes: [] };
    seat.on("response", (r) => {
      if (r.request().method() === "PATCH" && r.url().includes("/flows/"))
        person.writes.push(r.status());
    });
    await openFlowFor(seat, flowId);
    people.push(person);
  }
  return { flowId, people, contexts };
}

async function edit(person: Person, offset: number) {
  const node = person.page.locator(".react-flow__node").first();
  const box = await node.boundingBox();
  if (!box) throw new Error("no bounding box");
  await person.page.mouse.move(box.x + box.width / 2, box.y + 10);
  await person.page.mouse.down();
  await person.page.mouse.move(box.x + box.width / 2, box.y + 120 + offset * 25, { steps: 10 });
  await person.page.mouse.up();
}

async function trail(page: Page, flowId: string) {
  const response = await page.request.get(`/api/v1/flows/${flowId}/audit/`);
  if (response.status() === 404) test.skip(true, "audit trail not enabled on this backend");
  expect(response.status()).toBe(200);
  return (await response.json()).entries as any[];
}

async function inConflict(person: Person): Promise<boolean> {
  return person.page
    .getByTestId("flow-conflict-banner")
    .isVisible()
    .catch(() => false);
}

test("two people: one writes, the other is told and the trail shows one session", async ({
  page,
  browser,
}) => {
  test.setTimeout(6 * 60 * 1000);
  const { flowId, people, contexts } = await seatPeople(page, browser, 2);
  const [a, b] = people;

  await edit(a, 0);
  await a.page.waitForTimeout(SETTLE_MS);
  await edit(b, 1);
  await b.page.waitForTimeout(SETTLE_MS);

  const conflicted = [];
  for (const p of people) if (await inConflict(p)) conflicted.push(p.name);

  const entries = await trail(page, flowId);
  console.log(
    "2 people | writes:", people.map((p) => `${p.name}=${JSON.stringify(p.writes)}`).join(" "),
    "| conflicted:", conflicted,
    "| audit entries:", entries.length,
    "| sources:", entries.map((e) => e.source),
  );

  expect(conflicted, "exactly one person is refused").toHaveLength(1);
  expect(entries.length, "only the accepted write is recorded").toBe(1);
  expect(entries[0].source).toBe("editor");
  expect(entries[0].username).toBeTruthy();
  for (const c of contexts) await c.close();
});

test("three people: two lose the race, each takes a different exit", async ({
  page,
  browser,
}) => {
  test.setTimeout(8 * 60 * 1000);
  const { flowId, people, contexts } = await seatPeople(page, browser, 3);
  const [a, b, c] = people;

  await edit(a, 0);
  await a.page.waitForTimeout(SETTLE_MS);
  await Promise.all([edit(b, 1), edit(c, 2)]);
  await b.page.waitForTimeout(SETTLE_MS);
  await c.page.waitForTimeout(SETTLE_MS);

  expect(await inConflict(b), "b must be refused").toBe(true);
  expect(await inConflict(c), "c must be refused").toBe(true);

  // b updates the flow, c gives up and takes the latest.
  await b.page.getByTestId("flow-conflict-review-button").click();
  await b.page.getByTestId("confirm-overwrite-flow").click();
  await expect(b.page.getByTestId("flow-conflict-banner")).toBeHidden({
    timeout: CONFLICT_WINDOW_MS,
  });

  await c.page.getByTestId("flow-conflict-review-button").click();
  await c.page.getByTestId("discard-my-changes").click();
  await c.page.getByTestId("confirm-discard-my-changes").click();
  await expect(c.page.getByTestId("flow-conflict-banner")).toBeHidden({
    timeout: CONFLICT_WINDOW_MS,
  });

  const entries = await trail(page, flowId);
  const sources = entries.map((e) => e.source).sort();
  console.log(
    "3 people | audit entries:", entries.length, "| sources:", sources,
    "| c wrote nothing:", c.writes.filter((s) => s === 200).length === 0,
  );

  // Two writes happened: a's edit and b's update. c discarded, so nothing of c's.
  expect(sources, "the trail records both writers and only them").toEqual(["editor", "overwrite"]);
  expect(c.writes.filter((s) => s === 200), "discarding writes nothing").toHaveLength(0);
  for (const ctx of contexts) await ctx.close();
});

test("four people: everyone edits at once, nobody's work vanishes silently", async ({
  page,
  browser,
}) => {
  test.setTimeout(10 * 60 * 1000);
  const { flowId, people, contexts } = await seatPeople(page, browser, 4);

  // All four edit within the same debounce window.
  await Promise.all(people.map((p, i) => edit(p, i)));
  for (const p of people) await p.page.waitForTimeout(SETTLE_MS / 2);
  await page.waitForTimeout(SETTLE_MS);

  const conflicted: string[] = [];
  const accepted: string[] = [];
  for (const p of people) {
    if (await inConflict(p)) conflicted.push(p.name);
    if (p.writes.filter((s) => s === 200).length > 0) accepted.push(p.name);
  }

  const entries = await trail(page, flowId);
  const server = await (await page.request.get(`/api/v1/flows/${flowId}`)).json();
  const allWrites = people.flatMap((p) => p.writes);

  console.log(
    "4 people | writes:", people.map((p) => `${p.name}=${JSON.stringify(p.writes)}`).join(" "),
    "\n         | accepted:", accepted, "conflicted:", conflicted,
    "\n         | audit entries:", entries.length,
    "| server token:", server.version_token?.slice(0, 8),
  );

  // 1. No server error, ever.
  expect(allWrites.filter((s) => s >= 500), "no 5xx under four writers").toHaveLength(0);
  // 2. Everyone who was refused knows it.
  const refused = people.filter((p) => p.writes.includes(409)).map((p) => p.name);
  expect(conflicted.sort(), "every refused person sees the banner").toEqual(refused.sort());
  // 3. Nobody is left in the dark: accepted or told.
  for (const p of people) {
    const wasAccepted = p.writes.includes(200);
    const wasTold = conflicted.includes(p.name);
    expect(wasAccepted || wasTold, `${p.name} must be either accepted or told`).toBe(true);
  }
  // 4. The trail describes exactly the writes that landed, and no secret.
  expect(entries.length, "one entry per accepted writer's session").toBe(accepted.length);
  expect(JSON.stringify(entries)).not.toMatch(/sk-[a-z]/i);

  for (const ctx of contexts) await ctx.close();
});
