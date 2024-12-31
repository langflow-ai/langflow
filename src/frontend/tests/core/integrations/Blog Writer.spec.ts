import { test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "Blog Writer",
  { tag: ["@release", "@starter-project"] },
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
    await page.getByRole("heading", { name: "Blog Writer" }).click();

    await initialGPTsetup(page);

    await page
      .getByTestId("inputlist_str_urls_0")
      .nth(0)
      .fill(
        "https://www.natgeokids.com/uk/discover/animals/sea-life/turtle-facts/",
      );
    await page
      .getByTestId("inputlist_str_urls_1")
      .nth(0)
      .fill("https://www.originaldiving.com/blog/top-ten-turtle-facts");

    await page
      .getByTestId("textarea_str_input_value")
      .fill(
        "Use the references above for style to write a new blog/tutorial about turtles. Suggest non-covered topics.",
      );

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 30000,
    });

    await page.getByText("Playground", { exact: true }).last().click();
    await page
      .getByPlaceholder(
        "No chat input variables found. Click to run your flow.",
        { exact: true },
      )
      .last()
      .isVisible();

    await page.getByText("turtles").last().isVisible();
    await page.getByText("sea").last().isVisible();
    await page.getByText("survival").last().isVisible();
  },
);
