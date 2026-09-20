import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";

test(
  "user should be able to use chat memory as expected",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await adjustScreenView(page);

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

    await configureLoopbackOpenAI(page, {
      skipAdjustScreenView: true,
    });

    // ConfigureLoopbackOpenAI reloads the persisted graph. Add Message History
    // afterwards so an in-flight autosave cannot be overwritten by that
    // deterministic provider patch.
    await addComponentFromSidebar(page, {
      search: "message history",
      testId: "models_and_agentsMessage History",
      hoverAdd: true,
      addButtonSlug: "message-history",
    });
    const memoryNode = page.getByRole("application", {
      name: "Message History node",
    });
    await expect(memoryNode).toBeAttached();

    const prompt = `
{context}

User: {user_input}

AI:
  `;

    await page.getByTestId("title-Prompt Template").last().click();
    await page.getByTestId("button_open_prompt_modal").nth(0).click();

    await page.getByTestId("modal-promptarea_prompt_template").fill(prompt);
    await page.getByText(TEXTS.editPrompt, { exact: true }).click();
    await page.getByText(TEXTS.checkAndSave).last().click();

    await adjustScreenView(page);

    //connection 1
    await memoryNode
      .getByTestId("handle-memory-shownode-messages-right")
      .click();

    await page.getByTestId("handle-prompt-shownode-context-left").click();

    await page.locator('//*[@id="react-flow-id"]').hover();

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await sendPlaygroundMessage(
      page,
      "hi, my car is blue and I like to eat pizza",
    );
    await sendPlaygroundMessage(
      page,
      "what color is my car and what do I like to eat?",
    );

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
