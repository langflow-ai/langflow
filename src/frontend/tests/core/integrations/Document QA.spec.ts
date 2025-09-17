import * as dotenv from "dotenv";
import path from "path";
import { test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { uploadFile } from "../../utils/upload-file";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Document Q&A",
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
    await page.getByRole("heading", { name: "Document Q&A" }).click();
    await initialGPTsetup(page);

    await uploadFile(page, "test_file.txt");

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 3000,
    });

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page
      .getByText("No input message provided.", { exact: true })
      .last()
      .isVisible();

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

    await page.getByText("this is a test file").last().isVisible();

    await page.getByText("Default Session").last().click();

    await page.getByText("timestamp", { exact: true }).last().isVisible();
    await page.getByText("text", { exact: true }).last().isVisible();
    await page.getByText("sender", { exact: true }).last().isVisible();
    await page.getByText("sender_name", { exact: true }).last().isVisible();
    await page.getByText("session_id", { exact: true }).last().isVisible();
    await page.getByText("files", { exact: true }).last().isVisible();

    await page.getByRole("gridcell").last().isVisible();
    await page.getByRole("combobox").click();
    await page.getByLabel("Delete").click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page.getByTestId("input-chat-playground").last().isVisible();
  },
);
