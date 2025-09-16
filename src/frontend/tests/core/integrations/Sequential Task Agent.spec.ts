import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test.skip(
  "Sequential Task Agent",
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
      .getByRole("heading", { name: "Sequential Tasks Agent" })
      .first()
      .click();

    await initialGPTsetup(page);

    await page.getByTestId("button_run_chat output").click();

    await page.waitForTimeout(1000);

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByRole("button", { name: "Playground", exact: true }).click();

    expect(await page.locator(".markdown").count()).toBeGreaterThan(0);

    expect(await page.getByText("Agile").count()).toBeGreaterThan(0);
  },
);
