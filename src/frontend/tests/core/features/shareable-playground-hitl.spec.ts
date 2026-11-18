import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TID } from "../../utils/constants/testIds";
import { TIMEOUTS } from "../../utils/constants/timeouts";

type ComponentTemplate = {
  template: Record<string, { value?: unknown; input_types?: string[] }>;
};

const encodeHandle = (handle: Record<string, unknown>) =>
  JSON.stringify(
    Object.fromEntries(
      Object.entries(handle).sort(([a], [b]) => a.localeCompare(b)),
    ),
  ).replace(/"/g, "œ");

const node = (id: string, type: string, template: ComponentTemplate) => ({
  id,
  type: "genericNode",
  position: { x: 0, y: 0 },
  data: { id, type, node: template },
});

function edge(
  source: string,
  dataType: string,
  output: string,
  target: string,
  field: string,
  inputTypes: string[],
) {
  const sourceHandle = {
    dataType,
    id: source,
    name: output,
    output_types: ["Message"],
  };
  const targetHandle = {
    fieldName: field,
    id: target,
    inputTypes,
    type: "str",
  };
  return {
    id: `${source}-${output}-${target}`,
    source,
    target,
    sourceHandle: encodeHandle(sourceHandle),
    targetHandle: encodeHandle(targetHandle),
    data: { sourceHandle, targetHandle },
  };
}

/** Public flow: Chat Input -> Human Input -> one Chat Output per branch, each with its own sender name. */
async function createPublicApprovalFlow(page: Page): Promise<string> {
  const all = (await (await page.request.get("/api/v1/all")).json()) as Record<
    string,
    Record<string, ComponentTemplate>
  >;
  const find = (name: string) =>
    structuredClone(
      Object.values(all).find((category) => name in category)?.[name],
    ) as ComponentTemplate;
  const chatInput = find("ChatInput");
  const humanInput = find("HumanInput");
  const approve = find("ChatOutput");
  const reject = find("ChatOutput");
  approve.template.sender_name.value = "BRANCH-APPROVE";
  reject.template.sender_name.value = "BRANCH-REJECT";
  const outputTypes = approve.template.input_value.input_types ?? ["Message"];

  const created = await page.request.post("/api/v1/flows/", {
    data: {
      name: `shared-hitl-${Date.now()}`,
      access_type: "PUBLIC",
      data: {
        nodes: [
          node("In", "ChatInput", chatInput),
          node("Ask", "HumanInput", humanInput),
          node("OutYes", "ChatOutput", approve),
          node("OutNo", "ChatOutput", reject),
        ],
        edges: [
          edge("In", "ChatInput", "message", "Ask", "prompt", ["Message"]),
          edge(
            "Ask",
            "HumanInput",
            "branch_approve",
            "OutYes",
            "input_value",
            outputTypes,
          ),
          edge(
            "Ask",
            "HumanInput",
            "branch_reject",
            "OutNo",
            "input_value",
            outputTypes,
          ),
        ],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
    },
  });
  expect(created.status()).toBe(201);
  return (await created.json()).id;
}

async function ask(page: Page, question: string) {
  const input = page.getByTestId(TID.inputChatPlayground);
  await input.waitFor({ state: "visible", timeout: TIMEOUTS.long });
  await input.fill(question);
  await page.getByTestId(TID.buttonSend).last().click();
}

test(
  "shareable playground: a signed-in visitor gets the Human Input decision and the chosen branch runs",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });
    const flowId = await createPublicApprovalFlow(page);

    try {
      await page.goto(`/playground/${flowId}/`);
      await ask(page, "wipe staging?");

      const approveButton = page.getByRole("button", {
        name: "Approve",
        exact: true,
      });
      await expect(approveButton).toBeVisible({ timeout: TIMEOUTS.long });
      await expect(page.getByText("BRANCH-APPROVE")).toHaveCount(0);
      await expect(page.getByText("BRANCH-REJECT")).toHaveCount(0);
      await page.runA11yScan("shareable-playground-human-input-pending");

      await approveButton.click();

      await expect(page.getByText("BRANCH-APPROVE")).toBeVisible({
        timeout: TIMEOUTS.long,
      });
      await expect(page.getByText("BRANCH-REJECT")).toHaveCount(0);
    } finally {
      await page.request.delete(`/api/v1/flows/${flowId}`);
    }
  },
);

test(
  "shareable playground: an anonymous visitor is told a Human Input flow cannot run",
  { tag: ["@release", "@api"] },
  async ({ page, browser }, testInfo) => {
    await awaitBootstrapTest(page, { skipModal: true });
    const flowId = await createPublicApprovalFlow(page);
    const visitorContext = await browser.newContext({
      baseURL: testInfo.project.use.baseURL,
    });

    try {
      const visitor = await visitorContext.newPage();
      // A login-required deployment refuses auto-login, so the visitor stays anonymous.
      await visitor.route("**/api/v1/auto_login", (route) =>
        route.fulfill({
          status: 403,
          contentType: "application/json",
          body: JSON.stringify({
            detail: { message: "Auto login is disabled.", auto_login: false },
          }),
        }),
      );
      const runRequests: string[] = [];
      visitor.on("request", (request) => {
        if (new URL(request.url()).pathname.startsWith("/api/v2/workflows")) {
          runRequests.push(request.url());
        }
      });

      await visitor.goto(`/playground/${flowId}/`);
      await ask(visitor, "wipe staging?");

      await expect(
        visitor.getByRole("alert").filter({
          hasText: "This flow needs a human decision",
        }),
      ).toBeVisible({ timeout: TIMEOUTS.standard });
      expect(runRequests).toEqual([]);
    } finally {
      await visitorContext.close();
      await page.request.delete(`/api/v1/flows/${flowId}`);
    }
  },
);
