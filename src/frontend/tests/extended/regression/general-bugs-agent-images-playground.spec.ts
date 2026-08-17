import path from "path";
import { expect, test } from "../../fixtures";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TID } from "../../utils/constants/testIds";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";

test(
  "user must be able to send images in the playground with the agent component",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await openStarterProject(page, "Simple Agent");
    await configureLoopbackOpenAI(page, { skipUpdateOldComponents: true });

    await page.getByTestId(TID.playgroundBtnFlowIo).click();

    await page.waitForSelector(`[data-testid="${TID.inputChatPlayground}"]`, {
      timeout: TIMEOUTS.componentMount,
    });

    const filePath = path.resolve(__dirname, "../../assets/chain.png");
    await page.locator('input[type="file"]').setInputFiles(filePath);
    await expect(page.locator('img[alt$="chain.png"]')).toBeVisible({
      timeout: TIMEOUTS.standard,
    });

    await page.getByTestId(TID.inputChatPlayground).fill("what is this image?");

    await page.waitForSelector(`[data-testid="${TID.buttonSend}"]`, {
      timeout: TIMEOUTS.componentMount,
    });

    await page.getByTestId(TID.buttonSend).click();
    const response = page.locator(".markdown.prose").last();
    await expect(response).toContainText("loopback image received", {
      ignoreCase: true,
      timeout: TIMEOUTS.buildComplete,
    });
    await expect(response).toContainText("chain.png", { ignoreCase: true });
  },
);
