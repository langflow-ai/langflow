import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TIMEOUTS } from "../../utils/constants/timeouts";

type Template = {
  template: Record<string, { value?: unknown; input_types?: string[] }>;
};

const encodeHandle = (handle: Record<string, unknown>) =>
  JSON.stringify(
    Object.fromEntries(
      Object.entries(handle).sort(([a], [b]) => a.localeCompare(b)),
    ),
  ).replace(/"/g, "œ");

/** Chat Input -> If-Else (matches "yes") -> one Chat Output per branch. */
async function createIfElseFlow(page: Page): Promise<string> {
  const all = (await (await page.request.get("/api/v1/all")).json()) as Record<
    string,
    Record<string, Template>
  >;
  const find = (name: string) =>
    structuredClone(
      Object.values(all).find((category) => name in category)![name],
    );
  const chatInput = find("ChatInput");
  const chatOutput = find("ChatOutput");
  const ifElse = find("ConditionalRouter");
  ifElse.template.match_text.value = "yes";
  ifElse.template.operator.value = "equals";

  const edge = (
    source: string,
    dataType: string,
    output: string,
    target: string,
    field: string,
    inputTypes: string[],
  ) => {
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
      type: field === "input_text" ? "str" : "other",
    };
    return {
      id: `${source}-${output}-${target}`,
      source,
      target,
      sourceHandle: encodeHandle(sourceHandle),
      targetHandle: encodeHandle(targetHandle),
      data: { sourceHandle, targetHandle },
    };
  };
  const node = (id: string, type: string, tpl: Template, x: number, y = 0) => ({
    id,
    type: "genericNode",
    position: { x, y },
    data: { id, type, node: tpl },
  });
  const outputTypes = chatOutput.template.input_value.input_types!;

  const created = await page.request.post("/api/v1/flows/", {
    data: {
      name: `play-untaken-branch-${Date.now()}`,
      data: {
        nodes: [
          node("ChatInput-in", "ChatInput", chatInput, 0),
          node("ConditionalRouter-r", "ConditionalRouter", ifElse, 400),
          node("ChatOutput-T", "ChatOutput", chatOutput, 800),
          node("ChatOutput-F", "ChatOutput", chatOutput, 800, 350),
        ],
        edges: [
          edge(
            "ChatInput-in",
            "ChatInput",
            "message",
            "ConditionalRouter-r",
            "input_text",
            ifElse.template.input_text.input_types!,
          ),
          edge(
            "ConditionalRouter-r",
            "ConditionalRouter",
            "true_result",
            "ChatOutput-T",
            "input_value",
            outputTypes,
          ),
          edge(
            "ConditionalRouter-r",
            "ConditionalRouter",
            "false_result",
            "ChatOutput-F",
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

test(
  "play on a branch the router did not take says which branch it took",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });
    const flowId = await createIfElseFlow(page);
    await page.goto(`/flow/${flowId}`);

    // An empty Chat Input does not match "yes", so If-Else takes False.
    const untaken = page.locator('[data-id="ChatOutput-T"]');
    await untaken.hover();
    await untaken.getByTestId("button_run_chat output").click();

    const blocked = untaken.getByTestId("node_status_icon_chat output_inactive");
    await expect(blocked).toBeVisible({ timeout: TIMEOUTS.long });
    await blocked.hover();

    const tooltip = page.getByRole("tooltip");
    await expect(tooltip).toContainText("Branch not taken");
    await expect(tooltip).toContainText("If-Else sent the input to False.");
  },
);
