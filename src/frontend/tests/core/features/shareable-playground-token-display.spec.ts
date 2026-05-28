import { expect, test } from "../../fixtures";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { buildFlowAndWait } from "../../utils/flow/build-flow-and-wait";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
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

test(
  "regular playground: Finished In with token display still works (regression)",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);

    await openStarterProject(page, "Basic Prompting");
    await initialGPTsetup(page);

    await buildFlowAndWait(page);

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await page.waitForSelector(`[data-testid="${TID.inputChatPlayground}"]`, {
      timeout: TIMEOUTS.medium,
    });

    await page.getByTestId(TID.inputChatPlayground).click();
    await page.getByTestId(TID.inputChatPlayground).fill("Say hello briefly");
    await page.keyboard.press("Enter");

    await page.waitForFunction(
      () =>
        document.querySelectorAll('[data-testid="div-chat-message"]').length >=
        2,
      { timeout: TIMEOUTS.buildComplete },
    );

    await expect(page.getByText("Finished in")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
  },
);
