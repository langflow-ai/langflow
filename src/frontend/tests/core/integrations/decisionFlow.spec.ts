import { Page, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

// Enhanced wait function with better error handling and retries
async function waitForElement(
  page: Page,
  elementId: string,
  nth: number,
  maxRetries = 3,
) {
  let lastError;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const element = page.getByTestId(`title-${elementId}`).nth(nth);

      // First wait for the element to be attached to DOM
      await element.waitFor({
        state: "attached",
        timeout: 10000,
      });

      // Then wait for it to be visible
      await element.waitFor({
        state: "visible",
        timeout: 20000,
      });

      // Additional stability check
      const isVisible = await element.isVisible();
      if (!isVisible) {
        throw new Error(`Element ${elementId} is not visible after waiting`);
      }

      // Wait for any animations to complete
      await page.waitForTimeout(1500);

      return element;
    } catch (error) {
      lastError = error;
      console.log(
        `Attempt ${attempt + 1} failed for element ${elementId}. Retrying...`,
      );
      await page.waitForTimeout(2000); // Wait before retry
    }
  }
  throw lastError;
}

// Improved version of moveElementByXY with better error handling and waits
async function moveElementByXY(
  page: Page,
  elementId: string,
  moveX: number,
  moveY: number,
  nth: number,
) {
  try {
    const element = await waitForElement(page, elementId, nth);
    await element.hover();

    const boundingBox = await element.boundingBox();
    if (!boundingBox) {
      throw new Error(
        `Unable to get bounding box for the element: ${elementId}`,
      );
    }

    const startX = boundingBox.x + boundingBox.width / 2;
    const startY = boundingBox.y + boundingBox.height / 2;

    await page.mouse.move(startX, startY);
    await page.waitForTimeout(100);
    await page.mouse.down();
    await page.waitForTimeout(100);

    // Move in smaller increments
    const steps = 5;
    const stepX = moveX / steps;
    const stepY = moveY / steps;
    for (let i = 1; i <= steps; i++) {
      await page.mouse.move(startX + stepX * i, startY + stepY * i);
      await page.waitForTimeout(50);
    }

    await page.mouse.up();
    await page.waitForTimeout(100);
  } catch (error) {
    console.error(`Failed to move element ${elementId}:`, error);
    throw error;
  }
}

// Enhanced move function with retries and stability checks
async function moveElementByX(
  page: Page,
  elementId: string,
  moveX: number,
  nth: number,
) {
  const maxRetries = 3;
  let lastError;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const element = await waitForElement(page, elementId, nth);

      // Ensure the page is stable
      await page.waitForLoadState("networkidle");

      await element.hover();
      await page.waitForTimeout(500);

      const boundingBox = await element.boundingBox();
      if (!boundingBox) {
        throw new Error(`Unable to get bounding box for element: ${elementId}`);
      }

      const startX = boundingBox.x + boundingBox.width / 2;
      const startY = boundingBox.y + boundingBox.height / 2;

      // More granular mouse movements
      await page.mouse.move(startX, startY);
      await page.waitForTimeout(100);
      await page.mouse.down();
      await page.waitForTimeout(100);

      // Move in smaller increments with pauses
      const steps = 5;
      const stepX = moveX / steps;
      for (let i = 1; i <= steps; i++) {
        await page.mouse.move(startX + stepX * i, startY);
        await page.waitForTimeout(100);
      }

      await page.mouse.up();
      await page.waitForTimeout(500);

      // Verify the move was successful
      const newBoundingBox = await element.boundingBox();
      if (
        !newBoundingBox ||
        Math.abs(newBoundingBox.x - boundingBox.x - moveX) > 50
      ) {
        throw new Error("Move operation did not complete successfully");
      }

      return;
    } catch (error) {
      lastError = error;
      console.log(
        `Move attempt ${attempt + 1} failed for ${elementId}. Retrying...`,
      );
      await page.waitForTimeout(2000);
      await page.getByTestId("fit_view").click();
      throw lastError;
    }
  }
}

test("should create a flow with decision", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );
  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }
  await page.goto("/");
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
  //---------------------------------- CHAT INPUT
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat input");
  await page.waitForTimeout(500);
  await page
    .getByTestId("inputsChat Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //---------------------------------- CREATE LIST
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("list");
  await page.waitForTimeout(500);
  await page
    .getByTestId("helpersCreate List")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.getByTestId("input-list-plus-btn_texts-0").first().click();
  await page.getByTestId("input-list-plus-btn_texts-0").first().click();
  await page.getByTestId("input-list-plus-btn_texts-0").first().click();
  await page
    .getByTestId("inputlist_str_texts_0")
    .first()
    .fill("big news! langflow 1.0 is out");
  await page
    .getByTestId("inputlist_str_texts_1")
    .first()
    .fill("uhul that movie was awesome");
  await page.getByTestId("inputlist_str_texts_2").first().fill("love you babe");
  await page
    .getByTestId("helpersCreate List")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.getByTestId("input-list-plus-btn_texts-0").last().click();
  await page.getByTestId("input-list-plus-btn_texts-0").last().click();
  await page.getByTestId("input-list-plus-btn_texts-0").last().click();
  await page.getByTestId("inputlist_str_texts_0").last().fill("oh my cat died");
  await page
    .getByTestId("inputlist_str_texts_1")
    .last()
    .fill("No one loves me");
  await page.getByTestId("inputlist_str_texts_2").last().fill("not cool..");
  //---------------------------------- PARSE DATA
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("parse data");
  await page.waitForTimeout(500);
  await page
    .getByTestId("helpersParse Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page
    .getByTestId("helpersParse Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //---------------------------------- PASS
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("pass");
  await page.waitForTimeout(500);
  await page
    .getByTestId("prototypesPass")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.waitForTimeout(500);
  await page
    .getByTestId("prototypesPass")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.waitForTimeout(500);
  await page
    .getByTestId("prototypesPass")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //---------------------------------- PROMPT
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("prompt");
  await page.waitForTimeout(500);
  await page
    .getByTestId("promptsPrompt")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //---------------------------------- OPENAI
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("openai");
  await page.waitForTimeout(500);
  await page
    .getByTestId("modelsOpenAI")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //---------------------------------- CONDITIONAL ROUTER
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("conditional router");
  await page.waitForTimeout(500);
  await page
    .getByTestId("prototypesConditional Router")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //---------------------------------- CHAT OUTPUT
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat output");
  await page.waitForTimeout(500);
  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.waitForTimeout(500);
  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //----------------------------------
  await page.getByTestId("fit_view").click();
  await page.waitForTimeout(500);
  await moveElementByX(page, "Chat Output", 400, 1);
  await page.waitForTimeout(500);
  await moveElementByX(page, "Chat Output", 700, 0);
  await page.waitForTimeout(500);
  await moveElementByX(page, "Conditional Router", 1100, 0);
  await page.waitForTimeout(500);
  await page.getByTestId("fit_view").click();
  await moveElementByX(page, "OpenAI", 980, 0);
  await page.getByTestId("fit_view").click();
  await page.waitForTimeout(500);
  await moveElementByX(page, "Prompt", 990, 0);
  await page.getByTestId("fit_view").click();
  await page.waitForTimeout(500);
  await moveElementByX(page, "Pass", 1000, 2);
  await page.getByTestId("fit_view").click();
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Pass", 0, 200, 1);
  await page.getByTestId("fit_view").click();
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Pass", 150, 200, 0);
  await page.getByTestId("fit_view").click();
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Parse Data", 300, 200, 1);
  await page.getByTestId("fit_view").click();
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Parse Data", 450, 200, 0);
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Create List", 600, 200, 1);
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Create List", 800, 200, 0);
  await page.waitForTimeout(500);
  await page.getByTestId("fit_view").click();
  //---------------------------------- EDIT PROMPT
  await page.getByTestId("promptarea_prompt_template").first().click();
  await page.getByTestId("modal-promptarea_prompt_template").first().fill(`
      {Condition}
  Answer with either TRUE or FALSE (and nothing else).
  TRUE Examples:
  {true_examples}
  FALSE Examples:
  {false_examples}
  User: {user_message}
  AI:
      `);
  await page.getByText("Check & Save").last().click();
  //---------------------------------- MAKE CONNECTIONS
  await page
    .getByTestId("handle-createlist-shownode-data list-right")
    .nth(0)
    .click();
  await page.getByTestId("handle-parsedata-shownode-data-left").nth(0).click();
  await page
    .getByTestId("handle-createlist-shownode-data list-right")
    .nth(2)
    .click();
  await page.getByTestId("handle-parsedata-shownode-data-left").nth(1).click();
  await page
    .getByTestId("handle-chatinput-shownode-message-right")
    .nth(0)
    .click();
  await page
    .getByTestId("handle-pass-shownode-input message-left")
    .nth(2)
    .click();
  await page.getByTestId("handle-parsedata-shownode-text-right").nth(0).click();
  await page
    .getByTestId("handle-prompt-shownode-true_examples-left")
    .nth(0)
    .click();
  await page.getByTestId("handle-parsedata-shownode-text-right").nth(2).click();
  await page
    .getByTestId("handle-prompt-shownode-false_examples-left")
    .nth(0)
    .click();
  await page
    .getByTestId("handle-pass-shownode-output message-right")
    .nth(4)
    .click();
  await page
    .getByTestId("handle-prompt-shownode-user_message-left")
    .nth(0)
    .click();
  await page
    .getByTestId("handle-prompt-shownode-prompt message-right")
    .first()
    .click();
  await page
    .getByTestId("handle-openaimodel-shownode-input-left")
    .nth(0)
    .click();
  await page
    .getByTestId("handle-openaimodel-shownode-text-right")
    .nth(0)
    .click();
  await page
    .getByTestId("handle-conditionalrouter-shownode-input text-left")
    .nth(0)
    .click();
  await page.getByTestId("popover-anchor-input-match_text").fill("TRUE");
  await page.getByTestId("title-Pass").nth(1).click();
  await page.getByTestId("edit-button-modal").click();
  await page
    .getByTestId("popover-anchor-input-input_message-edit")
    .nth(0)
    .fill("You're Happy! 🤪");
  await page.getByTestId("showignored_message").last().click();
  await page.getByText("Close").last().click();
  await page.getByTestId("title-Pass").nth(0).click();
  await page.getByTestId("edit-button-modal").click();
  await page
    .getByTestId("popover-anchor-input-input_message-edit")
    .nth(0)
    .fill("You're Sad! 🥲");
  await page.getByTestId("showignored_message").last().click();
  await page.getByText("Close").last().click();
  await page
    .getByTestId("handle-conditionalrouter-shownode-true route-right")
    .nth(0)
    .click();
  await page
    .getByTestId("handle-pass-shownode-ignored message-left")
    .nth(1)
    .click();
  await page
    .getByTestId("handle-conditionalrouter-shownode-false route-right")
    .nth(0)
    .click();
  await page
    .getByTestId("handle-pass-shownode-ignored message-left")
    .nth(0)
    .click();
  await page
    .getByTestId("handle-pass-shownode-output message-right")
    .nth(2)
    .click();
  await page.getByTestId("handle-chatoutput-shownode-text-left").nth(0).click();
  await page
    .getByTestId("handle-pass-shownode-output message-right")
    .nth(0)
    .click();
  await page.getByTestId("handle-chatoutput-shownode-text-left").nth(1).click();
  const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
  const isApiKeyInputVisible = await apiKeyInput.isVisible();
  if (isApiKeyInputVisible) {
    await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
  }
  await page.getByTestId("dropdown_str_model_name").click();
  await page.getByTestId("gpt-4o-1-option").click();
  await page.getByTestId("fit_view").click();
  await page.getByText("Playground", { exact: true }).last().click();
  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });
  await page.getByTestId("input-chat-playground").click();
  await page
    .getByTestId("input-chat-playground")
    .fill("my dog is alive and happy!");
  await page.waitForSelector('[data-testid="button-send"]', {
    timeout: 100000,
  });

  await page.getByTestId("button-send").last().click();
});
