import { expect } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Simple Agent",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await openStarterProject(page, "Simple Agent");
    await initialGPTsetup(page);

    await page.getByTestId("playground-btn-flow-io").click();

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("Hello, tell me about Langflow.");

    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: TEXTS.stop });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });

    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 120000 });
    }

    const textContents = await page.getByTestId("div-chat-message").innerText();

    expect(await page.getByTestId("header-icon").last().isVisible());
    expect(await page.getByTestId("duration-display").last().isVisible());
    expect(await page.getByTestId("icon-check").nth(0).isVisible());
    expect(await page.getByTestId("icon-Check").nth(0).isVisible());
    expect(textContents.length).toBeGreaterThan(30);
  },
);
