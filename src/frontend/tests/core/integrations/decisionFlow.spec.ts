import { test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "should create a flow with decision",
  { tag: ["@release", "@components", "@workflow"] },

  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    //---------------------------------- CHAT INPUT
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");
    await page.waitForSelector('[data-testid="input_outputChat Input"]', {
      timeout: 2000,
    });

    await zoomOut(page, 6);

    await page
      .getByTestId("input_outputChat Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    //---------------------------------- CREATE LIST
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("list");
    await page.waitForSelector('[data-testid="helpersCreate List"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("helpersCreate List")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 100 },
      });

    await page.waitForSelector('[data-testid="input-list-plus-btn_texts-0"]', {
      timeout: 3000,
      state: "attached",
    });

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
    await page
      .getByTestId("inputlist_str_texts_2")
      .first()
      .fill("love you babe");
    await page
      .getByTestId("helpersCreate List")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 350, y: 100 },
      });
    await page.getByTestId("input-list-plus-btn_texts-0").last().click();
    await page.getByTestId("input-list-plus-btn_texts-0").last().click();
    await page.getByTestId("input-list-plus-btn_texts-0").last().click();
    await page
      .getByTestId("inputlist_str_texts_0")
      .last()
      .fill("oh my cat died");
    await page
      .getByTestId("inputlist_str_texts_1")
      .last()
      .fill("No one loves me");
    await page.getByTestId("inputlist_str_texts_2").last().fill("not cool..");
    //---------------------------------- PARSE DATA
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("data to message");
    await page.waitForSelector('[data-testid="processingData to Message"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("processingData to Message")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 500, y: 100 },
      });
    await page
      .getByTestId("processingData to Message")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 650, y: 100 },
      });

    //---------------------------------- PASS
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("pass");
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("logicPass")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 800, y: 100 },
      });
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 2000,
    });
    //---------------------------------- PASS
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("pass");
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("logicPass")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 200 },
      });
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 2000,
    });
    //---------------------------------- PASS
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("pass");
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("logicPass")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 200, y: 300 },
      });
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 2000,
    });
    //---------------------------------- PROMPT
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("prompt");
    await page.waitForSelector('[data-testid="processingPrompt Template"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("processingPrompt Template")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 350, y: 300 },
      });

    //---------------------------------- OPENAI
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("openai");
    await page.waitForSelector('[data-testid="openai_openai_draggable"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("openaiOpenAI")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 500, y: 300 },
      });

    //---------------------------------- CONDITIONAL ROUTER
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("if else");
    await page.waitForSelector('[data-testid="logicIf-Else"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("logicIf-Else")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 650, y: 300 },
      });
    //---------------------------------- CHAT OUTPUT
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("input_outputChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 800, y: 300 },
      });
    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 2000,
    });
    //---------------------------------- CHAT OUTPUT
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 2000,
    });
    await page
      .getByTestId("input_outputChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 800, y: 400 },
      });
    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 2000,
    });
    //----------------------------------
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
    await page
      .getByTestId("handle-parsedata-shownode-data-left")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-createlist-shownode-data list-right")
      .nth(1)
      .click();
    await page
      .getByTestId("handle-parsedata-shownode-data-left")
      .nth(1)
      .click();
    await page
      .getByTestId("handle-chatinput-noshownode-chat message-source")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-pass-shownode-input message-left")
      .nth(2)
      .click();
    await page
      .getByTestId("handle-parsedata-shownode-message-right")
      .nth(0)
      .click();
    //quebrando aqui
    await page
      .getByTestId("handle-prompt template-shownode-true_examples-left")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-parsedata-shownode-message-right")
      .nth(1)
      .click();
    await page
      .getByTestId("handle-prompt template-shownode-false_examples-left")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-pass-shownode-output message-right")
      .nth(2)
      .click();
    await page
      .getByTestId("handle-prompt template-shownode-user_message-left")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-prompt template-shownode-prompt-right")
      .first()
      .click();
    await page
      .getByTestId("handle-openaimodel-shownode-input-left")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-openaimodel-shownode-model response-right")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-conditionalrouter-shownode-text input-left")
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
      .getByTestId("handle-conditionalrouter-shownode-true-right")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-pass-shownode-ignored message-left")
      .nth(1)
      .click();
    await page
      .getByTestId("handle-conditionalrouter-shownode-false-right")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-pass-shownode-ignored message-left")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-pass-shownode-output message-right")
      .nth(1)
      .click();
    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-pass-shownode-output message-right")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .nth(1)
      .click();
    const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
    const isApiKeyInputVisible = await apiKeyInput.isVisible();
    if (isApiKeyInputVisible) {
      await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
    }
    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("gpt-4o-1-option").click();
    await page.getByTestId("fit_view").click();
    await page.getByRole("button", { name: "Playground", exact: true }).click();
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
  },
);
