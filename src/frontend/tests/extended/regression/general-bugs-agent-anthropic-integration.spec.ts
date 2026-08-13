import { expect, test } from "../../fixtures";
import {
  configureLoopbackOpenAI,
  LOOPBACK_OPENAI_API_KEY,
} from "../../utils/configure-loopback-openai";
import { TID } from "../../utils/constants/testIds";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { openStarterProject } from "../../utils/flow/open-starter-project";

test(
  "user can select Anthropic and run Simple Agent through the loopback provider",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await openStarterProject(page, "Simple Agent");

    const providerDropdown = page.getByTestId(
      "value-dropdown-dropdown_str_agent_llm",
    );
    await providerDropdown.click();
    await page.getByText("Anthropic", { exact: true }).last().click();
    await expect(providerDropdown).toContainText("Anthropic");
    const apiKeyInput = page.getByTestId(TID.popoverAnchorInputApiKey);
    await expect(apiKeyInput).toHaveAttribute("type", "password");
    await apiKeyInput.fill(LOOPBACK_OPENAI_API_KEY);

    await configureLoopbackOpenAI(page);

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
    expect(lengthOfTextFromLlm).toBeGreaterThan(30);
  },
);
