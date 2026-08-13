import { expect, type Page } from "@playwright/test";
import { addLegacyComponents } from "../add-legacy-components";
import { TEXTS } from "../constants/texts";
import { TIMEOUTS } from "../constants/timeouts";
import { addComponentFromSidebar } from "./add-component-from-sidebar";
import { openBlankFlow } from "./open-blank-flow";

async function addComponent(
  page: Page,
  options: {
    search: string;
    testId: string;
    addButtonSlug: string;
    displayName: string;
  },
): Promise<void> {
  const nodes = page.locator(".react-flow__node");
  const previousCount = await nodes.count();
  await addComponentFromSidebar(page, {
    search: options.search,
    testId: options.testId,
    hoverAdd: true,
    addButtonSlug: options.addButtonSlug,
  });
  await expect(nodes).toHaveCount(previousCount + 1);
  await expect(
    page.getByRole("group", { name: `${options.displayName} node` }),
  ).toBeAttached();
}

export async function createTextInputOutputFlow(page: Page): Promise<void> {
  await openBlankFlow(page);
  await addLegacyComponents(page);
  await addComponent(page, {
    search: TEXTS.searchTextInput,
    testId: "input_outputText Input",
    addButtonSlug: "text-input",
    displayName: "Text Input",
  });
  await addComponent(page, {
    search: TEXTS.searchPrompt,
    testId: "models_and_agentsPrompt Template",
    addButtonSlug: "prompt-template",
    displayName: "Prompt Template",
  });

  const textInputNode = page.getByRole("group", { name: "Text Input node" });
  const promptNode = page.getByRole("group", {
    name: "Prompt Template node",
  });
  await promptNode.click({ force: true });
  await promptNode.getByTestId("button_open_prompt_modal").click({
    force: true,
  });
  await page
    .getByTestId("modal-promptarea_prompt_template")
    .fill("{input_value}");
  await page.getByTestId("genericModalBtnSave").click();

  await textInputNode
    .getByTestId("handle-textinput-shownode-output text-right")
    .click({ force: true });
  await promptNode
    .getByTestId("handle-prompt-shownode-input_value-left")
    .click({ force: true });

  await addComponent(page, {
    search: TEXTS.searchTextOutput,
    testId: "input_outputText Output",
    addButtonSlug: "text-output",
    displayName: "Text Output",
  });
  const textOutputNode = page.getByRole("group", {
    name: "Text Output node",
  });
  await promptNode
    .getByTestId("handle-prompt-shownode-prompt-right")
    .click({ force: true });
  await textOutputNode
    .getByTestId("handle-textoutput-shownode-inputs-left")
    .click({ force: true });
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
}

export async function runTextInputOutputFlow(
  page: Page,
  value?: string,
): Promise<string> {
  if (value !== undefined) {
    await page
      .getByRole("group", { name: "Text Input node" })
      .getByTestId("textarea_str_input_value")
      .fill(value, { force: true });
  }
  const textOutputNodeId = await page
    .getByRole("group", { name: "Text Output node" })
    .getAttribute("data-id");
  if (!textOutputNodeId) {
    throw new Error("Text Output node is missing its React Flow data-id");
  }
  const [buildResponse] = await Promise.all([
    page.waitForResponse(
      (response) => {
        const path = new URL(response.url()).pathname;
        const vertexId = decodeURIComponent(path.split("/").at(-1) ?? "");
        return (
          response.request().method() === "POST" &&
          /^\/api\/v1\/build\/[^/]+\/vertices\//.test(path) &&
          vertexId === textOutputNodeId
        );
      },
      { timeout: TIMEOUTS.standard },
    ),
    page
      .getByRole("group", { name: "Text Output node" })
      .getByTestId("button_run_text output")
      .click({ force: true }),
  ]);
  expect(buildResponse.ok()).toBe(true);
  await page
    .getByTestId("output-inspection-output text-textoutput")
    .first()
    .click();
  const output = await page
    .getByPlaceholder(TEXTS.placeholderEmpty)
    .first()
    .inputValue();
  await page.getByRole("button", { name: TEXTS.close }).last().click();
  return output;
}

export async function freezePathFromTextOutput(
  page: Page,
  entryPoint: "toolbar" | "menu",
): Promise<void> {
  const freezeTarget =
    entryPoint === "menu" ? "Prompt Template" : "Text Output";
  const targetNode = page.locator(".react-flow__node").filter({
    has: page.getByText(freezeTarget, { exact: true }),
  });
  await targetNode.click({ force: true });

  let freezeButton = page
    .locator('[data-testid="freeze-all-button-modal"]:visible')
    .first();
  if (entryPoint === "menu") {
    await page.getByTestId("more-options-modal").click();
    freezeButton = page.getByTestId("freeze-path-button");
  }
  await expect(freezeButton).toBeVisible({ timeout: TIMEOUTS.standard });

  const [freezeResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        /\/api\/v1\/build\/[^/]+\/vertices$/.test(
          new URL(response.url()).pathname,
        ),
    ),
    freezeButton.click(),
  ]);
  expect(freezeResponse.ok()).toBe(true);
  await expect(page.getByTestId("icon-Snowflake").first()).toBeVisible();
}
