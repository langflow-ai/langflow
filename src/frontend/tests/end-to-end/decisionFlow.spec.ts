import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("should create a flow with decision", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

  await page.goto("/");
  await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
  await page.waitForTimeout(2000);

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
    await page.waitForTimeout(5000);
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
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chat input");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsChat Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("create list");
  await page.waitForTimeout(1000);

  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page
    .getByTestId("helpersCreate List")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTestId("input-list-plus-btn_texts-0").click();
  await page.getByTestId("input-list-plus-btn_texts-0").click();

  await page
    .getByTestId("input-list-input_texts-0")
    .fill("big news! langflow 1.0 is out");
  await page
    .getByTestId("input-list-input_texts-1")
    .fill("uhul that movie was awesome");
  await page.getByTestId("input-list-input_texts-2").fill("love you babe");

  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page
    .getByTestId("helpersCreate List")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTestId("input-list-plus-btn_texts-0").last().click();
  await page.getByTestId("input-list-plus-btn_texts-0").last().click();

  await page
    .getByTestId("input-list-input_texts-0")
    .last()
    .fill("oh my cat died");
  await page
    .getByTestId("input-list-input_texts-1")
    .last()
    .fill("No one loves me");
  await page.getByTestId("input-list-input_texts-2").last().fill("not cool..");

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("parse data");
  await page.waitForTimeout(1000);

  await page.getByTitle("zoom out").click();

  await page
    .getByTestId("helpersParse Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page
    .getByTestId("helpersParse Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("prompt");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("promptsPrompt")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("openai");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("modelsOpenAI")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("conditional router");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("prototypesConditional Router")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("pass");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("prototypesPass")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page
    .getByTestId("prototypesPass")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("zoom out").click();

  await page
    .getByTestId("prototypesPass")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("zoom out").click();

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chatoutput");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("zoom out").click();

  await page
    .getByTestId("outputsChat Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  //connection 1
  const elementCreateListOutput0 = await page
    .getByTestId("handle-createlist-shownode-data list-right")
    .nth(2);
  await elementCreateListOutput0.hover();
  await page.mouse.down();
  const elementParseDataInput0 = await page
    .getByTestId("handle-parsedata-shownode-data-left")
    .nth(0);
  await elementParseDataInput0.hover();
  await page.mouse.up();

  //connection 2
  const elementCreateListOutput1 = await page
    .getByTestId("handle-createlist-shownode-data list-right")
    .first();
  await elementCreateListOutput1.hover();
  await page.mouse.down();
  const elementParseDataInput1 = await page
    .getByTestId("handle-parsedata-shownode-data-left")
    .last();
  await elementParseDataInput1.hover();
  await page.mouse.up();

  //connection 3
  const elementChatInputOutput = await page
    .getByTestId("handle-chatinput-shownode-message-right")
    .first();
  await elementChatInputOutput.hover();
  await page.mouse.down();
  const elementPassInput3 = await page
    .getByTestId("handle-pass-shownode-input message-left")
    .last();
  await elementPassInput3.hover();
  await page.mouse.up();

  //connection 4
  const elementPassOutput3 = await page
    .getByTestId("handle-pass-shownode-output message-right")
    .nth(4);
  await elementPassOutput3.hover();
  await page.mouse.down();
  const elementConditionalRouterInput = await page
    .getByTestId("handle-conditionalrouter-shownode-message-left")
    .first();
  await elementConditionalRouterInput.hover();
  await page.mouse.up();

  //edit prompt
  await page.getByTestId("prompt-input-template").first().click();
  await page.getByTestId("modal-prompt-input-template").first().fill(`
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

  await page.locator('//*[@id="react-flow-id"]').hover();

  //connection 5
  const elementParseDataOutput0 = await page
    .getByTestId("handle-parsedata-shownode-text-right")
    .nth(0);
  await elementParseDataOutput0.hover();
  await page.mouse.down();
  const elementPromptInput = await page
    .getByTestId("handle-prompt-shownode-false_examples-left")
    .first();
  await elementPromptInput.hover();
  await page.mouse.up();

  await page.locator('//*[@id="react-flow-id"]').hover();

  //connection 6
  const elementParseDataOutput1 = await page
    .getByTestId("handle-parsedata-shownode-text-right")
    .nth(2);
  await elementParseDataOutput1.hover();
  await page.mouse.down();
  const elementPromptInput1 = await page
    .getByTestId("handle-prompt-shownode-true_examples-left")
    .first();
  await elementPromptInput1.hover();
  await page.mouse.up();

  await page.locator('//*[@id="react-flow-id"]').hover();

  //connection 7
  elementPassOutput3.hover();
  await page.mouse.down();
  const elementPromptInput2 = await page
    .getByTestId("handle-prompt-shownode-user_message-left")
    .first();
  await elementPromptInput2.hover();
  await page.mouse.up();

  await page.locator('//*[@id="react-flow-id"]').hover();

  //connection 8
  const elementPromptOutput = await page
    .getByTestId("handle-prompt-shownode-prompt message-right")
    .first();
  await elementPromptOutput.hover();
  await page.mouse.down();
  const elementOpenAiInput = await page
    .getByTestId("handle-openaimodel-shownode-input-left")
    .first();
  await elementOpenAiInput.hover();
  await page.mouse.up();

  await page.locator('//*[@id="react-flow-id"]').hover();

  //connection 9
  const elementPassOutput1 = await page
    .getByTestId("handle-pass-shownode-output message-right")
    .nth(2);
  await elementPassOutput1.hover();
  await page.mouse.down();
  const elementChatOutput = await page
    .getByTestId("handle-chatoutput-shownode-text-left")
    .last();
  await elementChatOutput.hover();
  await page.mouse.up();

  await page.locator('//*[@id="react-flow-id"]').hover();

  //connection 10
  const elementPassOutput2 = await page
    .getByTestId("handle-pass-shownode-output message-right")
    .first();
  await elementPassOutput2.hover();
  await page.mouse.down();
  const elementChatOutput1 = await page
    .getByTestId("handle-chatoutput-shownode-text-left")
    .first();
  await elementChatOutput1.hover();
  await page.mouse.up();

  await page.locator('//*[@id="react-flow-id"]').hover();

  //connection 11
  const elementOpenAiOutput = await page
    .getByTestId("handle-openaimodel-shownode-text-right")
    .first();
  await elementOpenAiOutput.hover();
  await page.mouse.down();
  const elementConditionalRouterInput1 = await page
    .getByTestId("handle-conditionalrouter-shownode-input text-left")
    .first();
  await elementConditionalRouterInput1.hover();
  await page.mouse.up();

  await page.getByTestId("icon-arrow-right").nth(1).click();
  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  let showIgnoredMessageCheckbox = await page.getByTestId(
    "showignored_message",
  );

  if (!(await showIgnoredMessageCheckbox.isChecked())) {
    await showIgnoredMessageCheckbox.click();
  }

  await page
    .getByTestId("popover-anchor-input-input_message-edit")
    .nth(0)
    .fill("You're Happy! 🤪");
  await page.getByText("Close").last().click();

  await page.getByTitle("zoom in").click();
  await page.getByTitle("zoom in").click();
  await page.getByTitle("zoom in").click();
  await page.getByTitle("zoom in").click();

  await page.locator('//*[@id="react-flow-id"]').hover();

  await page.getByTestId("icon-arrow-right").nth(0).click();
  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  showIgnoredMessageCheckbox = await page.getByTestId("showignored_message");

  if (!(await showIgnoredMessageCheckbox.isChecked())) {
    await showIgnoredMessageCheckbox.click();
  }

  await page
    .getByTestId("popover-anchor-input-input_message-edit")
    .nth(0)
    .fill("You're Sad! 🥲");
  await page.getByText("Close").last().click();

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTitle("fit view").click({
    force: true,
  });

  await page.getByTestId("popover-anchor-input-match_text").fill("TRUE");

  await page.locator('//*[@id="react-flow-id"]').hover();

  //connection 12
  const elementConditionalRouterOutput1 = await page
    .getByTestId("handle-conditionalrouter-shownode-true route-right")
    .first();
  await elementConditionalRouterOutput1.hover();
  await page.mouse.down();

  await page.locator('//*[@id="react-flow-id"]').hover();

  const elementPassInput1 = await page
    .getByTestId("handle-pass-shownode-ignored message-left")
    .nth(1);
  await elementPassInput1.hover();
  await page.mouse.up();

  await page.locator('//*[@id="react-flow-id"]').hover();

  //connection 13
  const elementConditionalRouterOutput2 = await page
    .getByTestId("handle-conditionalrouter-shownode-false route-right")
    .first();
  await elementConditionalRouterOutput2.hover();
  await page.mouse.down();
  const elementPassInput2 = await page
    .getByTestId("handle-pass-shownode-ignored message-left")
    .first();
  await elementPassInput2.hover();
  await page.mouse.up();

  await page.locator('//*[@id="react-flow-id"]').hover();

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByLabel("fit view").click();
  await page.getByText("Playground", { exact: true }).click();
  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });
  await page.getByTestId("input-chat-playground").click();

  await page.getByTestId("input-chat-playground").fill("my dog just dead");

  await page.waitForSelector('[data-testid="icon-LucideSend"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-LucideSend").click();

  await page.waitForSelector("text=🥲", {
    timeout: 100000,
  });

  await page.getByText("🥲").isVisible();
});
