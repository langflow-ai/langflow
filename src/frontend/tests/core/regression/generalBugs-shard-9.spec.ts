import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
test(
  "memory should work as expect",
  { tag: ["@release"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 2000,
    });

    await page.getByTestId("fit_view").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("message history");

    await page.getByTestId("sidebar-options-trigger").click();
    await page
      .getByTestId("sidebar-legacy-switch")
      .isVisible({ timeout: 5000 });
    await page.getByTestId("sidebar-legacy-switch").click();

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

    // End point (move 600 pixels to the right)
    const endX = startX + 600;
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
      .getByTestId("helpersMessage History")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 600 },
      });

    await initialGPTsetup(page, {
      skipAdjustScreenView: true,
    });

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

    await page.getByTestId("fit_view").click();

    //connection 1
    const elementChatMemoryOutput = await page
      .getByTestId("handle-memory-shownode-message-right")
      .first();
    await elementChatMemoryOutput.hover();
    await page.mouse.down();

    const promptInput = await page.getByTestId(
      "handle-prompt-shownode-context-left",
    );

    await promptInput.hover();
    await page.mouse.up();

    await page.locator('//*[@id="react-flow-id"]').hover();

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

    await page.waitForSelector("text=AI", { timeout: 30000 });

    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 100000,
    });

    // Wait for the first chat message element to be available
    const firstChatMessage = page.getByTestId("div-chat-message").nth(0);
    await firstChatMessage.waitFor({ state: "visible", timeout: 10000 });

    // Get the text from the second message (the response to the question about car color and food)
    const secondChatMessage = page.getByTestId("div-chat-message").nth(1);
    await secondChatMessage.waitFor({ state: "visible", timeout: 10000 });
    const memoryResponseText = await secondChatMessage.textContent();

    expect(memoryResponseText).not.toBeNull();
    expect(memoryResponseText?.includes("pizza")).toBeTruthy();
    expect(memoryResponseText?.includes("blue")).toBeTruthy();
  },
);
