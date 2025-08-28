import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "user should be able to analyze text sentiment",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Text Sentiment Analysis" })
      .click();
    await initialGPTsetup(page);

    await page.getByTestId("input-file-component").last().click();
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByTestId("drag-files-component").last().click();

    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(
      path.join(__dirname, "../../assets/test_file.txt"),
    );
    await page.getByText("test_file.txt").last().isVisible();

    await page.waitForTimeout(500);
    await page.getByTestId("select-files-modal-button").click();

    await page.waitForSelector('[data-testid="title-Chat Output"]', {
      timeout: 3000,
    });

    await page.getByTestId("title-Chat Output").last().click();
    await page.getByTestId("icon-MoreHorizontal").click();
    await page.getByText("Expand").click();

    await page.getByTestId("button_run_chat output").last().click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page
      .getByText("Add a Chat Input component to your flow to send messages.", {
        exact: true,
      })
      .last()
      .isVisible();

    const textAnalysis = await page.locator(".markdown").last().textContent();
    expect(textAnalysis?.length).toBeGreaterThan(50);
  },
);
