import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("should copy code from playground modal", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

  await page.goto("/");
  await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });

  await page.getByTestId("blank-flow").click();
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat output");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat input");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsChat Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("openai");
  await page.waitForTimeout(1000);

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  await page
    .getByTestId("modelsOpenAI")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }

  let filledApiKey = await page.getByTestId("remove-icon-badge").count();
  while (filledApiKey > 0) {
    await page.getByTestId("remove-icon-badge").first().click();
    await page.waitForTimeout(1000);
    filledApiKey = await page.getByTestId("remove-icon-badge").count();
  }

  const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
  const isApiKeyInputVisible = await apiKeyInput.isVisible();

  if (isApiKeyInputVisible) {
    await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
  }

  await page.getByTestId("dropdown_str_model_name").click();
  await page.getByTestId("gpt-4o-1-option").click();

  const elementsChatInput = await page
    .locator('[data-testid="handle-chatinput-shownode-message-right"]')
    .all();

  let visibleElementHandle;

  for (const element of elementsChatInput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  // Click and hold on the first element
  await page.getByTestId("zoom_in").click();
  await page.getByTestId("zoom_in").click();

  await page.locator(".react-flow__pane").click();

  await visibleElementHandle.hover();
  await page.mouse.down();

  const elementsOpenAiInput = await page
    .locator('[data-testid="handle-openaimodel-shownode-input-left"]')
    .all();

  for (const element of elementsOpenAiInput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover();
  await page.mouse.up();

  const elementsOpenAiOutput = await page
    .locator('[data-testid="handle-openaimodel-shownode-text-right"]')
    .all();

  for (const element of elementsOpenAiOutput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  // Click and hold on the first element
  await visibleElementHandle.hover();
  await page.mouse.down();

  // Move to the second element
  const elementsChatOutput = await page
    .getByTestId("handle-chatoutput-shownode-text-left")
    .all();

  for (const element of elementsChatOutput) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover();
  await page.mouse.up();

  await page.getByTestId("fit_view").click();
  await page.getByText("Playground", { exact: true }).last().click();
  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });
  await page.getByTestId("input-chat-playground").click();
  await page
    .getByTestId("input-chat-playground")
    .fill("Could you provide a Python example for a 'Hello, World!' program?");

  await page.waitForSelector('[data-testid="button-send"]', {
    timeout: 100000,
  });

  await page.getByTestId("button-send").click();

  await page.getByRole("tab", { name: "python" }).isVisible({
    timeout: 100000,
  });

  await page.waitForSelector('[data-testid="copy-code-button"]', {
    state: "visible",
    timeout: 30000,
  });

  await page.waitForTimeout(1000);
  await page.getByTestId("copy-code-button").last().click();

  const handle = await page.evaluateHandle(() =>
    navigator.clipboard.readText(),
  );
  const clipboardContent = await handle.jsonValue();
  expect(clipboardContent.length).toBeGreaterThan(0);
  expect(clipboardContent).toContain("Hello");
});

test("playground button should be enabled or disabled", async ({ page }) => {
  await page.goto("/");
  await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });

  await page.getByTestId("blank-flow").click();

  expect(await page.getByTestId("playground-btn-flow").isDisabled());

  expect(await page.getByText("Langflow Chat").isHidden());

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat output");

  await page.waitForTimeout(1000);

  await page
    .locator('//*[@id="outputsChat Output"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.waitForTimeout(1000);

  await page.getByTestId("playground-btn-flow-io").click({ force: true });

  expect(await page.getByText("Langflow Chat").isVisible());
});
