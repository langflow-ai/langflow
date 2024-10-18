import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

// Add this function at the beginning of the file, after the imports
async function moveElementByX(
  page: any,
  elementId: string,
  moveX: number,
  nth: number,
) {
  const element = await page.getByTestId(`title-${elementId}`).nth(nth);
  await element.hover();

  const boundingBox = await element.boundingBox();

  if (boundingBox) {
    const startX = boundingBox.x + boundingBox.width / 2;
    const startY = boundingBox.y + boundingBox.height / 2;

    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + moveX, startY);
    await page.mouse.up();
  } else {
    throw new Error(`Unable to get bounding box for the element: ${elementId}`);
  }
}

// Add this function at the beginning of the file, after the imports
async function moveElementByY(
  page: any,
  elementId: string,
  moveY: number,
  nth: number,
) {
  const element = await page.getByTestId(`title-${elementId}`).nth(nth);
  await element.hover();

  const boundingBox = await element.boundingBox();

  if (boundingBox) {
    const startX = boundingBox.x + boundingBox.width / 2;
    const startY = boundingBox.y + boundingBox.height / 2;

    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, startY + moveY);
    await page.mouse.up();
  } else {
    throw new Error(`Unable to get bounding box for the element: ${elementId}`);
  }
}

// Add this function at the beginning of the file, after the imports
async function moveElementByXY(
  page: any,
  elementId: string,
  moveX: number,
  moveY: number,
  nth: number,
) {
  const element = await page.getByTestId(`title-${elementId}`).nth(nth);
  await element.hover();

  const boundingBox = await element.boundingBox();

  if (boundingBox) {
    const startX = boundingBox.x + boundingBox.width / 2;
    const startY = boundingBox.y + boundingBox.height / 2;

    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + moveX, startY + moveY);
    await page.mouse.up();
  } else {
    throw new Error(`Unable to get bounding box for the element: ${elementId}`);
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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }
  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });
  await page.getByTestId("blank-flow").click();
  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });
  await page.getByTestId("extended-disclosure").click();
  //---------------------------------- CHAT INPUT
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chat input");
  await page.waitForTimeout(500);
  await page
    .getByTestId("inputsChat Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  //---------------------------------- CREATE LIST
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("list");
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
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("parse data");
  await page.waitForTimeout(500);

  await page
    .getByTestId("helpersParse Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page
    .getByTestId("helpersParse Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  //---------------------------------- PASS
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("pass");
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
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("prompt");
  await page.waitForTimeout(500);
  await page
    .getByTestId("promptsPrompt")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //---------------------------------- OPENAI
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("openai");
  await page.waitForTimeout(500);
  await page
    .getByTestId("modelsOpenAI")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  //---------------------------------- CONDITIONAL ROUTER
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("conditional router");
  await page.waitForTimeout(500);
  await page
    .getByTestId("prototypesConditional Router")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //---------------------------------- CHAT OUTPUT
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chat output");
  await page.waitForTimeout(500);
  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.waitForTimeout(500);
  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  //----------------------------------

  await page.getByTitle("fit view").click();

  await moveElementByX(page, "Chat Output", 500, 1);
  await page.waitForTimeout(500);
  await moveElementByX(page, "Chat Output", 1000, 0);
  await page.waitForTimeout(500);
  await moveElementByX(page, "Conditional Router", 1500, 0);
  await page.waitForTimeout(500);
  await moveElementByX(page, "OpenAI", 2000, 0);
  await page.waitForTimeout(500);
  await moveElementByX(page, "Prompt", 2500, 0);
  await page.waitForTimeout(500);
  await moveElementByX(page, "Pass", 3000, 2);
  await page.getByTitle("fit view").click();
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Pass", 0, 200, 1);
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Pass", 150, 200, 0);
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Parse Data", 300, 200, 1);
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Parse Data", 450, 200, 0);
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Create List", 600, 200, 1);
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Create List", 800, 200, 0);
  await page.waitForTimeout(500);
  await moveElementByXY(page, "Chat Input", 1000, 200, 0);

  await page.waitForTimeout(500);
  await page.getByTitle("fit view").click();

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

  await page.getByTestId("advanced-button-modal").click();

  await page
    .getByTestId("popover-anchor-input-input_message-edit")
    .nth(0)
    .fill("You're Happy! 🤪");

  await page.getByTestId("showignored_message").last().click();

  await page.getByText("Close").last().click();

  await page.getByTestId("title-Pass").nth(0).click();

  await page.getByTestId("advanced-button-modal").click();

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

  await page
    .getByTestId("popover-anchor-input-api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");
  await page.getByTestId("dropdown_str_model_name").click();
  await page.getByTestId("gpt-4o-1-option").click();
  await page.getByLabel("fit view").click();
  await page.getByText("Playground", { exact: true }).last().click();
  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });
  await page.getByTestId("input-chat-playground").click();
  await page
    .getByTestId("input-chat-playground")
    .fill("my dog is alive and happy!");
  await page.waitForSelector('[data-testid="icon-LucideSend"]', {
    timeout: 100000,
  });
  await page.getByTestId("icon-LucideSend").click();
  await page.waitForSelector("text=🤪", {
    timeout: 1200000,
  });
  await page.getByText("🤪").isVisible();
});
