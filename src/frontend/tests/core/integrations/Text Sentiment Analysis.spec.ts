import { expect } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import { unselectNodes } from "../../utils/unselect-nodes";
import { uploadFile } from "../../utils/upload-file";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "user should be able to analyze text sentiment",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Text Sentiment Analysis" })
      .click();
    await configureLoopbackOpenAI(page);

    await uploadFile(page, "test_file.txt");

    await page.waitForSelector('[data-testid="title-Chat Output"]', {
      timeout: 3000,
    });

    await page.getByTestId("title-Chat Output").last().click();
    await page.getByTestId("icon-MoreHorizontal").click();
    await page.getByText("Expand").click();
    await unselectNodes(page);
    await page.getByTestId("button_run_chat output").last().click();
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 120000,
    });

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await page
      .getByText("Add a Chat Input component to your flow to send messages.", {
        exact: true,
      })
      .last()
      .isVisible();

    await page.waitForTimeout(5000);

    const textAnalysis = await page.locator(".markdown").last().textContent();
    expect(textAnalysis?.toLowerCase()).toContain("positive");
  },
);
