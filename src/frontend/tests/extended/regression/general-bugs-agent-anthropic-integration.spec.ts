import { expect, test } from "../../fixtures";
import { TID } from "../../utils/constants/testIds";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openStarterProject } from "../../utils/flow/open-starter-project";

test(
  "user must be able to run Simple Agent in the playground with Anthropic provider",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    skipIfMissing.anthropicKey();
    loadDotenvIfLocal(__dirname);

    await openStarterProject(page, "Simple Agent");

    await page.getByTestId("value-dropdown-dropdown_str_agent_llm").click();
    await page.getByText("Anthropic").last().click();

    await page
      .getByTestId(TID.popoverAnchorInputApiKey)
      .fill(process.env.ANTHROPIC_API_KEY || "");

    await page.getByTestId(TID.playgroundBtnFlowIo).click();

    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.componentMount,
    });

    await page.getByTestId(TID.buttonSend).click();

    await page.waitForSelector("text=Finished", { timeout: TIMEOUTS.short });

    const textFromLlm = await page
      .locator(".markdown.prose")
      .last()
      .textContent();

    const lengthOfTextFromLlm = textFromLlm?.length;
    expect(lengthOfTextFromLlm).toBeGreaterThan(100);
  },
);
