import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { addNewApiKeys } from "../../utils/add-new-api-keys";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { removeOldApiKeys } from "../../utils/remove-old-api-keys";
import { selectGptModel } from "../../utils/select-gpt-model";
import { updateOldComponents } from "../../utils/update-old-components";

test(
  "SEO Keyword Generator",
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
    await page.getByRole("heading", { name: "SEO Keyword Generator" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await adjustScreenView(page);
    await updateOldComponents(page);
    await removeOldApiKeys(page);
    await addNewApiKeys(page);
    await selectGptModel(page);

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.getByText("Playground", { exact: true }).last().click();
    await page
      .getByText("No input message provided.", { exact: true })
      .last()
      .isVisible();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    const textContents = await getAllResponseMessage(page);

    expect(textContents.length).toBeGreaterThan(200);
    expect(textContents).toContain("work");
  },
);
