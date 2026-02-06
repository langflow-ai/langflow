import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "fresh start playground",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");
    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input_outputChat Output")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-chat-output").click();
      });

    await zoomOut(page, 2);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");
    await page.waitForSelector('[data-testid="input_outputChat Input"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input_outputChat Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text output");
    await page.waitForSelector('[data-testid="input_outputText Output"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("input_outputText Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 300 },
      });

    await adjustScreenView(page);

    await page
      .getByTestId("handle-chatinput-noshownode-chat message-source")
      .click();

    await page.getByTestId("handle-textoutput-shownode-inputs-left").click();

    await page
      .getByTestId("handle-textoutput-shownode-output text-right")
      .click();
    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .click();

    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    //send message
    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("message 1");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("chat-message-User-message 1")).toBeVisible();

    //check edit message
    await page.getByTestId("chat-message-User-message 1").hover();
    await page.getByTestId("icon-Pen").first().click();
    await page.getByTestId("textarea").fill("edit_1");
    await page.getByTestId("save-button").click();
    await expect(page.getByTestId("chat-message-User-edit_1")).toBeVisible();

    // check cancel edit
    await page.getByTestId("chat-message-User-edit_1").hover();
    await page.getByTestId("icon-Pen").first().click();
    await page.getByTestId("textarea").fill("cancel_edit");
    await page.getByTestId("cancel-button").click();
    await expect(page.getByTestId("chat-message-User-edit_1")).toBeVisible();

    //check edit bot message
    await page.getByTestId("chat-message-AI-message 1").hover();
    await page.getByTestId("icon-Pen").last().click();
    await page.getByTestId("textarea").fill("edit_bot_1");
    await page.getByTestId("save-button").click();
    await expect(page.getByTestId("chat-message-AI-edit_bot_1")).toBeVisible();

    // check cancel edit bot
    await page.getByTestId("chat-message-AI-edit_bot_1").hover();
    await page.getByTestId("icon-Pen").last().click();
    await page.getByTestId("textarea").fill("edit_bot_cancel");
    await page.getByTestId("cancel-button").click();
    await expect(page.getByTestId("chat-message-AI-edit_bot_1")).toBeVisible();

    // check table messages view
    await page.getByTestId("chat-header-more-menu").click();
    await page.getByTestId("message-logs-option").click();
    await expect(page.getByText("Page 1 of 1", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Close" }).click();

    // create new session
    await page.getByTestId("session-selector-trigger").click();
    await page.getByText("New Session").click();
    await page.keyboard.press("Escape");
    await expect(page.getByTitle("New Session 0")).toBeVisible();

    // check rename session
    await page
      .getByTestId("input-chat-playground")
      .fill("session_after_delete");
    await page.keyboard.press("Enter");
    await page
      .getByTestId("chat-message-User-session_after_delete")
      .isVisible();
    await page.getByTestId("chat-header-more-menu").click();
    await page.getByTestId("rename-session-option").click();
    await page.getByTestId("session-rename-input").fill("my first session");
    await page.keyboard.press("Enter");
    await expect(
      page.getByTestId("session-selector").getByText("my first session"),
    ).toBeVisible();

    // check cancel rename (using Escape key)
    await page.getByTestId("chat-header-more-menu").click();
    await page.getByTestId("rename-session-option").click();
    await page.getByTestId("session-rename-input").fill("cancel name");
    await page.keyboard.press("Escape");
    await expect(
      page.getByTestId("session-selector").getByText("my first session"),
    ).toBeVisible();

    // check delete session
    await page.getByTestId("chat-header-more-menu").click();
    await page.getByTestId("delete-session-option").click();
    await expect(page.getByTitle("Default Session")).toBeVisible();

    //create new session
    await page.getByTestId("session-selector-trigger").click();
    await page.getByText("New Session", { exact: true }).click();
    await page.keyboard.press("Escape");
    await page.getByTestId("input-chat-playground").click();
    await page
      .getByTestId("input-chat-playground")
      .fill("session_after_delete");
    await page.keyboard.press("Enter");
    await expect(
      page.getByTestId("chat-message-User-session_after_delete"),
    ).toBeVisible();
  },
);
