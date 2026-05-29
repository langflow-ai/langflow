import { expect } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { buildFlowAndWait } from "../../utils/flow/build-flow-and-wait";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { uploadFile } from "../../utils/upload-file";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Document Q&A",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await openStarterProject(page, "Document Q&A");
    await initialGPTsetup(page);

    await uploadFile(page, "test_file.txt");

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 3000,
    });
    await buildFlowAndWait(page);

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await page
      .getByText(TEXTS.labelNoInputMessage, { exact: true })
      .last()
      .isVisible();

    // Create a new session first
    await page.getByTestId("new-chat").click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });
    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("whats the text in the file?");
    await page.getByTestId("button-send").last().click();

    await page.waitForSelector("text=this is a test file", {
      timeout: 10000,
    });

    await expect(page.getByText("this is a test file").last()).toBeVisible();
    expect(await page.getByTestId("div-chat-message").last().count()).toBe(1);
  },
);
