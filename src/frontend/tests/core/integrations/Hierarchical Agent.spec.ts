import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test.skip(
  "Hierarchical Tasks Agent",
  { tag: ["@release", "@starter-project"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.SEARCH_API_KEY,
      "SEARCH_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: "Hierarchical Tasks Agent" })
      .first()
      .click();
    await initialGPTsetup(page);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .last()
      .fill(process.env.SEARCH_API_KEY ?? "");

    await page.waitForTimeout(1000);

    await page.getByTestId("button_run_chat output").click();

    await page.waitForTimeout(1000);

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.getByText("Playground", { exact: true }).last().click();

    expect(await page.locator(".markdown").count()).toBeGreaterThan(0);

    expect(await page.getByText("Langflow").count()).toBeGreaterThan(2);
  },
);
