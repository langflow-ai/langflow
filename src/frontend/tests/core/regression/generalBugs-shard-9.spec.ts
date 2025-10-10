import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "user should be able to use chat memory as expected",
  { tag: ["@release", "@workspace", "@components"] },
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

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 2000,
    });

    await adjustScreenView(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("message history");

    await addLegacyComponents(page);

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

    await adjustScreenView(page);

    //connection 1
    await page
      .getByTestId("handle-memory-shownode-message-right")
      .first()
      .click();

    await page.getByTestId("handle-prompt-shownode-context-left").click();

    await page.locator('//*[@id="react-flow-id"]').hover();

    await page.getByRole("button", { name: "Playground", exact: true }).click();

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
