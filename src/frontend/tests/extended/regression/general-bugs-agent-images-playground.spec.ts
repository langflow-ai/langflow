import { readFileSync } from "fs";
import { expect, test } from "../../fixtures";
import { TID } from "../../utils/constants/testIds";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openStarterProject } from "../../utils/flow/open-starter-project";

test(
  "user must be able to send images in the playground with the agent component",
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

    // Read the image file as a binary string
    const filePath = "tests/assets/chain.png";
    const fileContent = readFileSync(filePath, "base64");

    // Create the DataTransfer and File objects within the browser context
    const dataTransfer = await page.evaluateHandle(
      ({ fileContent }) => {
        const dt = new DataTransfer();
        const byteCharacters = atob(fileContent);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const file = new File([byteArray], "chain.png", { type: "image/png" });
        dt.items.add(file);
        return dt;
      },
      { fileContent },
    );

    await page.waitForSelector(`[data-testid="${TID.inputChatPlayground}"]`, {
      timeout: TIMEOUTS.componentMount,
    });

    const element = await page.getByTestId(TID.inputChatPlayground);
    await element.dispatchEvent("drop", { dataTransfer });

    await page.getByTestId(TID.inputChatPlayground).fill("what is this image?");

    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.componentMount,
    });

    await page.getByTestId(TID.buttonSend).click();

    await page.waitForSelector("text=chain.png", {
      timeout: TIMEOUTS.standard,
    });

    await expect(page.getByText("chain.png")).toBeVisible();

    const textFromLlm = await page
      .locator(".markdown.prose")
      .last()
      .textContent();

    expect(textFromLlm?.toLowerCase()).toMatch(/(chain|inkscape|logo)/);
    const lengthOfTextFromLlm = textFromLlm?.length;
    expect(lengthOfTextFromLlm).toBeGreaterThan(100);
  },
);
