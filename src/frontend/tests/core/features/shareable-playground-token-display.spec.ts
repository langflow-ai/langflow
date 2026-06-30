import { expect, test } from "../../fixtures";
import { TID } from "../../utils/constants/testIds";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { publishBasicPromptingAndOpenShareablePlayground } from "../../utils/playground/publish-and-open-shareable";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";

test(
  "shareable playground: bot messages display token usage",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);

    const { playgroundPage } =
      await publishBasicPromptingAndOpenShareablePlayground(page, context);

    await sendPlaygroundMessage(playgroundPage, "Say hi", {
      surface: "shareable",
    });

    // Token count should be visible (Coins icon indicates token display)
    await playgroundPage.waitForSelector(`[data-testid="${TID.iconCoins}"]`, {
      timeout: TIMEOUTS.standard,
    });
    const coinsIcons = await playgroundPage
      .locator(`[data-testid="${TID.iconCoins}"]`)
      .count();
    expect(coinsIcons).toBeGreaterThan(0);

    await playgroundPage.close();
  },
);
