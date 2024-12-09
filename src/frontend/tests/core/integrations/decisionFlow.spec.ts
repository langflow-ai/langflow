import { Page, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

async function zoomOut(page: Page, times: number = 4) {
  for (let i = 0; i < times; i++) {
    await page.getByTestId("zoom_out").click();
  }
}

test(
  "should create a flow with decision",
  { tag: ["@release", "@components"] },

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

    await page.getByTestId("sidebar-options-trigger").click();
    await page
      .getByTestId("sidebar-legacy-switch")
      .isVisible({ timeout: 5000 });
    await page.getByTestId("sidebar-legacy-switch").click();

    //---------------------------------- CHAT INPUT
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");
    await page.waitForSelector('[data-testid="inputsChat Input"]', {
      timeout: 500,
    });
    await page
      .getByTestId("inputsChat Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await zoomOut(page);

    //---------------------------------- CREATE LIST
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("list");
    await page.waitForSelector('[data-testid="helpersCreate List"]', {
      timeout: 500,
    });
    await page
      .getByTestId("helpersCreate List")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
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
        targetPosition: { x: 300, y: 300 },
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
    await page.getByTestId("sidebar-search-input").fill("parse data");
    await page.waitForSelector('[data-testid="processingParse Data"]', {
      timeout: 500,
    });
    await page
      .getByTestId("processingParse Data")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 350, y: 100 },
      });
    await zoomOut(page, 1);
    await page
      .getByTestId("processingParse Data")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 300 },
      });
    await zoomOut(page, 2);

    //---------------------------------- PASS
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("pass");
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 500,
    });
    await page
      .getByTestId("logicPass")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 400, y: 100 },
      });
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 500,
    });
    //---------------------------------- PASS
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("pass");
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 500,
    });
    await page
      .getByTestId("logicPass")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 600, y: 200 },
      });
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 500,
    });
    //---------------------------------- PASS
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("pass");
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 500,
    });
    await page
      .getByTestId("logicPass")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 650, y: 350 },
      });
    await page.waitForSelector('[data-testid="logicPass"]', {
      timeout: 500,
    });
    zoomOut(page, 2);
    //---------------------------------- PROMPT
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("prompt");
    await page.waitForSelector('[data-testid="promptsPrompt"]', {
      timeout: 500,
    });
    await page
      .getByTestId("promptsPrompt")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 150 },
      });

    //---------------------------------- OPENAI
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("openai");
    await page.waitForSelector('[data-testid="modelsOpenAI"]', {
      timeout: 500,
    });
    await page
      .getByTestId("modelsOpenAI")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 300 },
      });

    //---------------------------------- CONDITIONAL ROUTER
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("if else");
    await page.waitForSelector('[data-testid="logicIf-Else"]', {
      timeout: 500,
    });
    await page
      .getByTestId("logicIf-Else")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 750, y: 150 },
      });
    //---------------------------------- CHAT OUTPUT
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 500,
    });
    await page
      .getByTestId("outputsChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 75 },
      });
    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 500,
    });
    //---------------------------------- CHAT OUTPUT
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 500,
    });
    await page
      .getByTestId("outputsChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 250, y: 75 },
      });
    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 500,
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
      .nth(2)
      .click();
    await page
      .getByTestId("handle-parsedata-shownode-data-left")
      .nth(1)
      .click();
    await page
      .getByTestId("handle-chatinput-shownode-message-right")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-pass-shownode-input message-left")
      .nth(2)
      .click();
    await page
      .getByTestId("handle-parsedata-shownode-text-right")
      .nth(0)
      .click();
    //quebrando aqui
    await page
      .getByTestId("handle-prompt-shownode-true_examples-left")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-parsedata-shownode-text-right")
      .nth(2)
      .click();
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
      .nth(2)
      .click();
    await page
      .getByTestId("handle-chatoutput-shownode-text-left")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-pass-shownode-output message-right")
      .nth(0)
      .click();
    await page
      .getByTestId("handle-chatoutput-shownode-text-left")
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
  },
);
