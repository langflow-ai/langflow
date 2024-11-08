import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("memory should work as expect", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

  await page.goto("/");

  await page.waitForTimeout(1000);

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

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForTimeout(1000);

  await page.getByTestId("fit_view").click();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat memory");

  // Locate the canvas element
  const canvas = page.locator("#react-flow-id"); // Update the selector if needed

  // Get the bounding box of the canvas to determine its position
  const canvasBox = await canvas.boundingBox();
  if (!canvasBox) {
    throw new Error("Canvas element bounding box not found");
  }

  // Starting point (center of the canvas)
  const startX = canvasBox.x + canvasBox.width / 2;
  const startY = canvasBox.y + canvasBox.height / 2;

  // End point (move 300 pixels to the right)
  const endX = startX + 300;
  const endY = startY;

  // Hover over the canvas to focus it
  await canvas.hover();

  // Start the drag operation
  await page.mouse.move(startX, startY);
  await page.mouse.down();

  // Move to the new position
  await page.mouse.move(endX, endY);

  // Release the mouse button to finish the drag
  await page.mouse.up();

  await page
    .getByTestId("helpersChat Memory")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.waitForTimeout;

  await page.getByTestId("fit_view").click();

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

  const prompt = `
{context}

User: {user_input}

AI:
  `;

  await page.getByTestId("title-Prompt").last().click();
  await page.getByTestId("button_open_prompt_modal").nth(0).click();

  await page.getByTestId("modal-promptarea_prompt_template").fill(prompt);
  await page.getByText("Edit Prompt", { exact: true }).click();
  await page.getByText("Check & Save").last().click();

  //connection 1
  const elementChatMemoryOutput = await page
    .getByTestId("handle-memory-shownode-messages (text)-right")
    .first();
  await elementChatMemoryOutput.hover();
  await page.mouse.down();

  const promptInput = await page.getByTestId(
    "handle-prompt-shownode-context-left",
  );

  await promptInput.hover();
  await page.mouse.up();

  await page.locator('//*[@id="react-flow-id"]').hover();

  await page.waitForTimeout(1000);

  await page.getByText("Playground", { exact: true }).last().click();

  await page.waitForSelector('[data-testid="button-send"]', {
    timeout: 100000,
  });

  await page
    .getByPlaceholder("Send a message...")
    .fill("hi, my car is blue and I like to eat pizza");

  await page.getByTestId("button-send").click();

  await page.waitForSelector("text=AI", { timeout: 30000 });

  await page
    .getByPlaceholder("Send a message...")
    .fill("what color is my car and what do I like to eat?");

  await page.getByTestId("button-send").click();

  await page.waitForTimeout(400);

  const textLocator = page.locator("text=AI");
  await textLocator.nth(6).waitFor({ timeout: 30000 });
  await expect(textLocator.nth(1)).toBeVisible();

  await page.waitForTimeout(3000);

  const memoryResponseText = await page
    .locator(".form-modal-chat-text")
    .nth(1)
    .allTextContents();

  expect(memoryResponseText[0].includes("pizza")).toBeTruthy();
  expect(memoryResponseText[0].includes("blue")).toBeTruthy();
});
