import { expect, test } from "../../fixtures";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { waitForOpenModalWithChatInput } from "../../utils/wait-for-open-modal";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { openStarterProject } from "../../utils/flow/open-starter-project";

import { TEXTS } from "../../utils/constants/texts";
withEventDeliveryModes(
  "Prompt Chaining",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await page.goto("/");
    await openStarterProject(page, "Prompt Chaining");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 60000,
    });

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await page
      .getByText(TEXTS.labelNoInputMessage, { exact: true })
      .last()
      .isVisible();

    await waitForOpenModalWithChatInput(page);

    const textContents = await getAllResponseMessage(page);
    expect(textContents.length).toBeGreaterThan(100);
  },
);
