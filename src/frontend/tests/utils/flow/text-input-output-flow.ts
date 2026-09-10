import { expect, type Locator, type Page } from "@playwright/test";
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
    page.getByRole("application", { name: `${options.displayName} node` }),
  ).toBeAttached();
}

async function moveNodeBy(
  page: Page,
  node: Locator,
  deltaX: number,
): Promise<void> {
  const dragHandle = node.getByTestId("generic-node-title-arrangement");
  const before = await node.boundingBox();
  const handleBox = await dragHandle.boundingBox();
  if (!before || !handleBox) {
    throw new Error("Expected an attached graph node with a draggable title");
  }

  const startX = handleBox.x + handleBox.width / 2;
  const startY = handleBox.y + handleBox.height / 2;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX + deltaX, startY, { steps: 12 });
  await page.mouse.up();

  if (deltaX > 0) {
    await expect
      .poll(async () => (await node.boundingBox())?.x ?? before.x)
      .toBeGreaterThan(before.x + 100);
  } else {
    await expect
      .poll(async () => (await node.boundingBox())?.x ?? before.x)
      .toBeLessThan(before.x - 100);
  }
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
  const textInputNode = page.getByRole("application", {
    name: "Text Input node",
  });
  await moveNodeBy(page, textInputNode, -400);

  await addComponent(page, {
    search: TEXTS.searchPrompt,
    testId: "models_and_agentsPrompt Template",
    addButtonSlug: "prompt-template",
    displayName: "Prompt Template",
  });

  const promptNode = page.getByRole("application", {
    name: "Prompt Template node",
  });
  await promptNode
    .getByTestId("promptarea_prompt_template")
    .fill("{input_value}");

  await textInputNode
    .getByTestId("handle-textinput-shownode-output text-right")
    .click({ force: true });
  await promptNode
    .getByTestId("handle-prompt template-shownode-input_value-left")
    .click({ force: true });
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  await addComponent(page, {
    search: TEXTS.searchTextOutput,
    testId: "input_outputText Output",
    addButtonSlug: "text-output",
    displayName: "Text Output",
  });
  const textOutputNode = page.getByRole("application", {
    name: "Text Output node",
  });
  await moveNodeBy(page, textOutputNode, 400);
  await promptNode
    .getByTestId("handle-prompt template-shownode-prompt-right")
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
      .getByRole("application", { name: "Text Input node" })
      .getByTestId("textarea_str_input_value")
      .fill(value, { force: true });
  }
  const textOutputNode = page.getByRole("application", {
    name: "Text Output node",
  });
  const runButton = textOutputNode.getByRole("button", {
    name: "Run component",
  });
  await expect(runButton).toBeVisible();
  await expect(runButton).toBeEnabled();
  await expect(
    textOutputNode
      .getByTestId("button_run_text output")
      .getByTestId("icon-Play"),
  ).toBeVisible();
  const [buildResponse] = await Promise.all([
    page.waitForResponse(
      (response) => {
        const path = new URL(response.url()).pathname;
        return (
          response.request().method() === "POST" && path === "/api/v2/workflows"
        );
      },
      { timeout: TIMEOUTS.standard },
    ),
    runButton.click(),
  ]);
  expect(buildResponse.ok()).toBe(true);
  expect(await buildResponse.finished()).toBeNull();
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
