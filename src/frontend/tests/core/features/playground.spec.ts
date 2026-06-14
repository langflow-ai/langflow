import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { disableInspectPanel } from "../../utils/open-advanced-options";
import { sessionMoreMenu } from "../../utils/playground/sessions";
import { zoomOut } from "../../utils/zoom-out";

test(
  "fresh start playground",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    loadDotenvIfLocal(__dirname);

    await openBlankFlow(page);

    await addLegacyComponents(page);

    await disableInspectPanel(page);

    await addComponentFromSidebar(page, {
      search: "chat output",
      testId: "input_outputChat Output",
      hoverAdd: true,
    });

    await zoomOut(page, 2);

    await addComponentFromSidebar(page, {
      search: "chat input",
      testId: "input_outputChat Input",
      position: { x: 100, y: 100 },
    });

    await addComponentFromSidebar(page, {
      search: "text output",
      testId: "input_outputText Output",
      position: { x: 300, y: 300 },
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

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await page.waitForSelector(`[data-testid="${TID.inputChatPlayground}"]`, {
      timeout: TIMEOUTS.componentMount,
    });

    //send message
    await page.getByTestId(TID.inputChatPlayground).click();
    await page.getByTestId(TID.inputChatPlayground).fill("message 1");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("chat-message-User-message 1")).toBeVisible();
    await expect(page.getByTestId("chat-message-AI-message 1")).toBeVisible();

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

    // check table messages view (use sidebar session more menu — header menu hidden in fullscreen)
    await sessionMoreMenu(page, "first").click();
    await page.getByTestId("message-logs-option").click();
    await expect(page.getByText("Page 1 of 1", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: TEXTS.close }).click();

    // create new session (use sidebar new-chat button)
    await page.getByTestId(TID.newChat).click();
    await expect(page.getByTitle("New Session 0")).toBeVisible();

    // check rename session
    await page
      .getByTestId(TID.inputChatPlayground)
      .fill("session_after_delete");
    await page.keyboard.press("Enter");
    await page
      .getByTestId("chat-message-User-session_after_delete")
      .isVisible();
    // Use sidebar session more menu for rename
    await sessionMoreMenu(page, "last").click();
    await page.getByTestId("rename-session-option").click();
    await page.getByTestId("session-rename-input").fill("my first session");
    await page.keyboard.press("Enter");
    await expect(
      page
        .getByTestId(TID.sessionSelector)
        .filter({ hasText: "my first session" })
        .first(),
    ).toBeVisible({ timeout: 10000 });

    // check cancel rename (using Escape key)
    await sessionMoreMenu(page, "last").click();
    await page.getByTestId("rename-session-option").click();
    await page.getByTestId("session-rename-input").fill("cancel name");
    await page.keyboard.press("Escape");
    await expect(
      page
        .getByTestId(TID.sessionSelector)
        .filter({ hasText: "my first session" })
        .first(),
    ).toBeVisible({ timeout: 10000 });

    // check delete session
    await sessionMoreMenu(page, "last").click();
    await page.getByTestId("delete-session-option").click();
    await expect(page.getByTitle("Default Session")).toBeVisible();

    //create new session
    await page.getByTestId(TID.newChat).click();
    await page.getByTestId(TID.inputChatPlayground).click();
    await page
      .getByTestId(TID.inputChatPlayground)
      .fill("session_after_delete");
    await page.keyboard.press("Enter");
    await expect(
      page.getByTestId("chat-message-User-session_after_delete"),
    ).toBeVisible();
  },
);
