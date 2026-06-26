import { expect, test } from "../../fixtures";
import { TID } from "../../utils/constants/testIds";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { publishBasicPromptingAndOpenShareablePlayground } from "../../utils/playground/publish-and-open-shareable";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";

test(
  "shareable playground: auto-login user can send message and get response",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);

    const { playgroundPage } =
      await publishBasicPromptingAndOpenShareablePlayground(page, context);

    await sendPlaygroundMessage(playgroundPage, "Say hello", {
      surface: "shareable",
    });

    // After build complete, at least one chat message should be visible
    await expect(
      playgroundPage.locator(`[data-testid="${TID.chatMessage}"]`).first(),
    ).toBeVisible({ timeout: TIMEOUTS.medium });

    await playgroundPage.close();
  },
);

test(
  "shareable playground: streaming works",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);

    const { playgroundPage } =
      await publishBasicPromptingAndOpenShareablePlayground(page, context);

    await sendPlaygroundMessage(playgroundPage, "Tell me a short joke", {
      surface: "shareable",
    });

    // After stop button disappears the send button should be back
    await expect(
      playgroundPage.getByTestId(TID.buttonSend).last(),
    ).toBeVisible();

    await playgroundPage.close();
  },
);

test(
  "shareable playground: session management works",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);

    const { playgroundPage } =
      await publishBasicPromptingAndOpenShareablePlayground(page, context);

    await sendPlaygroundMessage(playgroundPage, "Session test", {
      surface: "shareable",
    });

    // Create new session
    await playgroundPage.getByTestId(TID.newChat).click();

    // New session should be created and the UI should not crash
    await expect(playgroundPage.getByTestId(TID.newChat)).toBeVisible();

    // Verify at least one session-selector exists
    await expect(
      playgroundPage.getByTestId(TID.sessionSelector).first(),
    ).toBeVisible({ timeout: TIMEOUTS.medium });

    await playgroundPage.close();
  },
);
