import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";
import { addNewApiKeys } from "../../utils/add-new-api-keys";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { buildDataTransfer } from "../../utils/build-data-transfer";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { removeOldApiKeys } from "../../utils/remove-old-api-keys";
import { selectGptModel } from "../../utils/select-gpt-model";
import { updateOldComponents } from "../../utils/update-old-components";
import { waitForOpenModalWithoutChatInput } from "../../utils/wait-for-open-modal";

test(
  "Image Sentiment Analysis",
  { tag: ["@release", "@starter-project"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByText("Image Sentiment Analysis", { exact: true })
      .last()
      .click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();

    await initialGPTsetup(page);

    await page.getByText("Playground", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    // Read the image file as a binary string
    const filePath = "tests/assets/chain.png";
    const fileContent = readFileSync(filePath, "base64");

    // Create the DataTransfer and File objects within the browser context
    const dataTransfer = await buildDataTransfer(page, fileContent);

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    // Locate the target element
    const element = await page.getByTestId("input-chat-playground");

    // Dispatch the drop event on the target element
    await element.dispatchEvent("drop", { dataTransfer });

    await waitForOpenModalWithoutChatInput(page);

    await page.getByTestId("button-send").click();

    await page.waitForSelector("text=chain.png", { timeout: 30000 });

    await page.getByText("chain.png").isVisible();

    await page.waitForSelector('[data-testid="div-chat-message"]', {
      timeout: 30000,
    });

    const textContents = await getAllResponseMessage(page);
    expect(textContents.length).toBeGreaterThan(10);
    expect(textContents.toLowerCase()).toContain("sentiment");
    expect(textContents.toLowerCase()).toContain("neutral");
    expect(textContents.toLowerCase()).toContain("description");
  },
);
