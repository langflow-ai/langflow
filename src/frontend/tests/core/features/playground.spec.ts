import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

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
    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("outputsChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await adjustScreenView(page);

    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");
    await page.waitForSelector('[data-testid="inputsChat Input"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("inputsChat Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text output");
    await page.waitForSelector('[data-testid="outputsText Output"]', {
      timeout: 100000,
    });

    await page
      .getByTestId("outputsText Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await adjustScreenView(page);

    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    const elementsChatInput = await page
      .locator('[data-testid="handle-chatinput-noshownode-message-source"]')
      .all();

    let visibleElementHandle;

    for (const element of elementsChatInput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    // Click and hold on the first element
    await visibleElementHandle.hover();
    await page.mouse.down();

    // Move to the second element

    const elementsTextOutput = await page
      .getByTestId("handle-textoutput-shownode-text-left")
      .all();

    for (const element of elementsTextOutput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    await visibleElementHandle.hover();

    // Release the mouse
    await page.mouse.up();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("fit_view").click();
    await page.getByTestId("fit_view").click();
    await page.getByTestId("fit_view").click();

    //

    const elementsTextOutputRight = await page
      .locator('[data-testid="handle-textoutput-shownode-text-right"]')
      .all();

    for (const element of elementsTextOutputRight) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    // Click and hold on the first element
    await visibleElementHandle.hover();
    await page.mouse.down();

    //
    const elementsChatOutput = await page
      .getByTestId("handle-chatoutput-noshownode-text-target")
      .all();

    for (const element of elementsChatOutput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    await visibleElementHandle.hover();

    // Release the mouse
    await page.mouse.up();

    await page.getByTestId("fit_view").click();
    await page.getByText("Playground", { exact: true }).last().click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    //send message
    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("message 1");
    await page.keyboard.press("Enter");
    //check message
    await page.getByTestId("chat-message-User-message 1").click();
    await page
      .getByTestId("chat-message-AI-message 1")
      .getByText("message")
      .click();
    //check session
    await page.getByText("Default Session").first().click();
    await page.getByTestId("chat-message-User-message 1").click();
    //check edit message
    await page.getByTestId("chat-message-User-message 1").hover();
    await page
      .locator("div")
      .filter({ hasText: /^Usermessage 1$/ })
      .getByTestId("icon-Pen")
      .click();

    await page.getByTestId("textarea").fill("edit_1");
    await page.getByTestId("save-button").click();
    await page.getByTestId("chat-message-User-edit_1").click();
    await page.getByTestId("chat-message-User-edit_1").hover();
    // check cancel edit
    await page.getByTestId("sender_name_user").hover();
    await page.getByTestId("icon-Pen").first().click();
    await page.getByTestId("textarea").fill("cancel_edit");
    await page.getByTestId("cancel-button").click();
    await page.getByTestId("chat-message-User-edit_1").click();
    await page.getByTestId("chat-message-User-edit_1").hover();
    //check edit bot message
    await page
      .getByTestId("chat-message-AI-message 1")
      .getByText("message")
      .click();
    await page.getByTestId("chat-message-AI-message 1").hover();
    await page.getByTestId("icon-Pen").last().click();

    await page.getByTestId("textarea").fill("edit_bot_1");
    await page.getByTestId("save-button").click();
    await page.getByText("edit_bot_1").click();
    // check cancel edit bot
    await page.getByTestId("chat-message-AI-edit_bot_1").hover();
    await page.getByTestId("icon-Pen").last().click();

    await page.getByTestId("textarea").fill("edit_bot_cancel");
    await page.getByTestId("cancel-button").click();
    await page.getByText("edit_bot_1").click();
    await page.getByTestId("chat-message-AI-edit_bot_1").hover();
    // check table messages view
    await page.getByRole("combobox").click();
    await page.getByLabel("Message logs").click();
    await page.getByText("Page 1 of 1", { exact: true }).click();
    // check rename session
    await page.getByRole("combobox").click();
    await page.getByLabel("Rename").getByText("Rename").click();
    await page.getByRole("textbox").fill("new name");
    await page.getByTestId("icon-Check").click();
    await page.waitForTimeout(500);

    await page.getByTestId("session-selector").getByText("new name").click();
    // check cancel rename
    await page.getByRole("combobox").click();
    await page.getByLabel("Rename").getByText("Rename").click();
    await page.getByRole("textbox").fill("cancel name");
    await page.getByTestId("session-selector").getByTestId("icon-X").click();
    await page.getByTestId("session-selector").getByText("new name").click();
    // check cancel rename blur
    await page.getByRole("combobox").click();
    await page.getByLabel("Rename").getByText("Rename").click();
    await page.getByRole("textbox").fill("cancel_blur");
    await page.getByText("PlaygroundChat").click();
    await page.getByTestId("session-selector").getByText("new name").click();
    // check delete session
    await page.getByRole("combobox").click();
    await page.getByLabel("Delete").click();
    await page.getByRole("heading", { name: "New chat" }).click();
    // check new session
    await page.getByTestId("input-chat-playground").click();
    await page
      .getByTestId("input-chat-playground")
      .fill("session_after_delete");
    await page.keyboard.press("Enter");
    await page.getByTestId("chat-message-User-session_after_delete").click();
    await expect(page.getByTestId("session-selector")).toBeVisible();

    // check helpful button
    await page.getByTestId("chat-message-AI-session_after_delete").hover();
    await page.getByTestId("helpful-button").click();
    await page.getByTestId("chat-message-AI-session_after_delete").hover();
    await expect(page.getByTestId("icon-ThumbUpIconCustom")).toBeVisible({
      timeout: 10000,
    });
    await page.getByTestId("helpful-button").click();
    await page.getByTestId("chat-message-AI-session_after_delete").hover();
    await expect(page.getByTestId("icon-ThumbUpIconCustom")).toBeVisible({
      timeout: 10000,
      visible: false,
    });
    // check not helpful button
    await page.getByTestId("chat-message-AI-session_after_delete").hover();
    await page.getByTestId("not-helpful-button").click();
    await page.getByTestId("chat-message-AI-session_after_delete").hover();
    await expect(page.getByTestId("icon-ThumbDownIconCustom")).toBeVisible({
      timeout: 10000,
    });
    await page.getByTestId("not-helpful-button").click();
    await page.getByTestId("chat-message-AI-session_after_delete").hover();
    await expect(page.getByTestId("icon-ThumbDownIconCustom")).toBeVisible({
      timeout: 10000,
      visible: false,
    });
    // check switch feedback
    await page.getByTestId("chat-message-AI-session_after_delete").hover();
    await page.getByTestId("helpful-button").click();
    await page.getByTestId("chat-message-AI-session_after_delete").hover();
    await expect(page.getByTestId("icon-ThumbUpIconCustom")).toBeVisible({
      timeout: 10000,
    });
    await page.getByTestId("not-helpful-button").click();
    await page.getByTestId("chat-message-AI-session_after_delete").hover();
    await expect(page.getByTestId("icon-ThumbDownIconCustom")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByTestId("icon-ThumbUpIconCustom")).toBeVisible({
      timeout: 10000,
      visible: false,
    });
  },
);
