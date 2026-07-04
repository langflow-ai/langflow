import fs from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// Two no-LLM agents (the same fixtures the backend a2a tests use, with canvas
// positions added so the editor can render them). Echo returns the caller's
// message; the human-input flow pauses for an approve/reject decision.
const readFlow = (name: string) =>
  JSON.parse(
    fs.readFileSync(path.join(__dirname, "../../assets/a2a", name), "utf-8"),
  );
const ECHO_FLOW = readFlow("echo-agent.json");
const HUMAN_INPUT_FLOW = readFlow("human-input-agent.json");

// Seed a flow straight through the API using the page's auto-login session, so
// we don't have to build a runnable agent by hand on the canvas.
async function seedFlow(
  page: Page,
  flow: unknown,
  opts: { flowType: "agent" | "workflow"; published?: boolean },
): Promise<string> {
  return page.evaluate(
    async ({ flow, opts }) => {
      const res = await fetch("/api/v1/flows/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(flow as Record<string, unknown>),
          flow_type: opts.flowType,
          a2a_enabled: !!opts.published,
        }),
      });
      if (!res.ok) throw new Error(`seed flow failed: ${res.status}`);
      return (await res.json()).id as string;
    },
    { flow, opts },
  );
}

async function openAgentTab(page: Page, flowId: string) {
  await page.goto(`/flow/${flowId}`);
  // The tab only mounts once the saved flow (flow_type=agent) is in the store.
  await expect(page.getByTestId("sidebar-nav-agent")).toBeVisible({
    timeout: 30000,
  });
  await page.getByTestId("sidebar-nav-agent").click();
  await expect(page.getByTestId("agent-publish-switch")).toBeVisible();
}

// If the flow's folder is apikey-gated, the live JSON-RPC endpoint needs an
// x-api-key. Mint one and paste it; on a public folder the field never shows.
async function fillTestKeyIfNeeded(page: Page) {
  const keyField = page.getByTestId("agent-test-apikey");
  if (await keyField.isVisible().catch(() => false)) {
    const key = await page.evaluate(async () => {
      const r = await fetch("/api/v1/api_key/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "a2a-e2e" }),
      });
      return (await r.json()).api_key as string;
    });
    await keyField.fill(key);
  }
}

async function sendMessage(page: Page, text: string) {
  await page.getByTestId("agent-test-input").fill(text);
  await page.getByTestId("agent-test-send").click();
}

test.describe("A2A Agent tab", () => {
  test(
    "shows the Agent tab only for agent flows",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });

      const agentId = await seedFlow(page, ECHO_FLOW, { flowType: "agent" });
      const workflowId = await seedFlow(page, ECHO_FLOW, {
        flowType: "workflow",
      });

      await page.goto(`/flow/${agentId}`);
      await expect(page.getByTestId("sidebar-nav-agent")).toBeVisible({
        timeout: 30000,
      });

      await page.goto(`/flow/${workflowId}`);
      await expect(page.getByTestId("sidebar-nav-components")).toBeVisible({
        timeout: 30000,
      });
      await expect(page.getByTestId("sidebar-nav-agent")).toHaveCount(0);
    },
  );

  test(
    "previews and publishes the agent card",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });
      const flowId = await seedFlow(page, ECHO_FLOW, {
        flowType: "agent",
        published: false,
      });
      await openAgentTab(page, flowId);

      // Draft: no live card, honest "publish to preview" note.
      await expect(page.getByTestId("agent-status")).toHaveText("Draft");
      await expect(
        page.getByText("Publish to preview the input contract", {
          exact: false,
        }),
      ).toBeVisible();

      // Publish + save.
      await page.getByTestId("agent-publish-switch").click();
      await page.getByTestId("agent-save").click();

      // Live: the resolved card is fetched, so the input contract appears.
      await expect(page.getByTestId("agent-status")).toHaveText("Live", {
        timeout: 30000,
      });
      await expect(page.getByText("Input contract")).toBeVisible();
      await expect(page.getByText("input_value")).toBeVisible();
      await expect(page.getByText("session_id")).toBeVisible();
      await expect(page.getByTestId("agent-card-url")).toHaveValue(
        /\/api\/v1\/a2a\/.+\/\.well-known\/agent-card\.json$/,
      );
    },
  );

  test(
    "runs a multi-turn conversation over the live endpoint",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });
      const flowId = await seedFlow(page, ECHO_FLOW, {
        flowType: "agent",
        published: true,
      });
      await openAgentTab(page, flowId);
      await fillTestKeyIfNeeded(page);

      const transcript = page.getByTestId("agent-transcript");

      await sendMessage(page, "hello a2a");
      // The echo agent completes and returns the message verbatim.
      await expect(transcript.getByText("completed")).toBeVisible({
        timeout: 60000,
      });
      await expect(transcript.getByText("hello a2a").last()).toBeVisible();

      // A second turn threads onto the same conversation (contextId).
      await sendMessage(page, "second turn");
      await expect(page.getByText("2 turns")).toBeVisible({ timeout: 60000 });
      await expect(transcript.getByText("second turn").last()).toBeVisible();
    },
  );

  test(
    "pauses on input-required and resumes to completed",
    { tag: ["@release", "@api"] },
    async ({ page }) => {
      await awaitBootstrapTest(page, { skipModal: true });
      const flowId = await seedFlow(page, HUMAN_INPUT_FLOW, {
        flowType: "agent",
        published: true,
      });
      await openAgentTab(page, flowId);
      await fillTestKeyIfNeeded(page);

      const transcript = page.getByTestId("agent-transcript");

      // The flow pauses for a decision and surfaces the prompt.
      await sendMessage(page, "start");
      await expect(transcript.getByText("needs input")).toBeVisible({
        timeout: 60000,
      });
      await expect(transcript.getByText("Approve this?").first()).toBeVisible();

      // Approving resumes the same task through to completion.
      await sendMessage(page, "Approve");
      await expect(transcript.getByText("completed")).toBeVisible({
        timeout: 60000,
      });
    },
  );
});
