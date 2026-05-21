import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to create a new flow clicking on New Flow button",
  { tag: ["@release", "@mainpage"] },
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
    await page.waitForSelector("text=playground", { timeout: 30000 });
    await page.waitForSelector("text=share", { timeout: 30000 });

    await expect(page.getByTestId("button_run_chat output")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("button_run_language model")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("button_run_prompt template")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByTestId("button_run_chat input")).toBeVisible({
      timeout: 30000,
    });
  },
);
