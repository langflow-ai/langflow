import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test.skip(
  "Dynamic Agent",
  { tag: ["@release", "@starter-projects"] },
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
    await page.getByRole("heading", { name: "Dynamic Agent" }).last().click();
    await initialGPTsetup(page);

    await page
      .getByTestId("popover-anchor-input-api_key")
      .last()
      .fill(process.env.SEARCH_API_KEY ?? "");

    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill("how much is an apple stock today");
    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", {
      timeout: 60000 * 3,
    });

    await page.getByRole("button", { name: "Playground", exact: true }).click();
    await page.waitForTimeout(1000);
    expect(page.getByText("apple").last()).toBeVisible();
    const textContents = await page
      .getByTestId("div-chat-message")
      .allTextContents();
    const concatAllText = textContents.join(" ");
    expect(concatAllText.toLocaleLowerCase()).toContain("apple");
    expect(concatAllText.toLocaleLowerCase()).not.toContain("error");
    expect(concatAllText.toLocaleLowerCase()).not.toContain("apologize");
    const allTextLength = concatAllText.length;
    expect(allTextLength).toBeGreaterThan(100);
  },
);
