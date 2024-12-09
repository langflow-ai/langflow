import { test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "user must be able to see output inspection",
  { tag: ["@release", "@components"] },
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
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await initialGPTsetup(page);

    await page.getByTestId("button_run_chat output").last().click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.waitForSelector('[data-testid="icon-ScanEye"]', {
      timeout: 30000,
    });

    await page.getByTestId("icon-ScanEye").nth(4).click();

    await page.getByText("Sender", { exact: true }).isVisible();
    await page.getByText("Type", { exact: true }).isVisible();
    await page.getByText("User", { exact: true }).last().isVisible();
  },
);
