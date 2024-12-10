import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "user must be able to freeze a path",
  { tag: ["@release", "@workspace", "@components"] },

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

    await initialGPTsetup(page);

    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill(
        "say a random number between 1 and 100000 and a random animal that lives in the sea",
      );

    await page.getByTestId("dropdown_str_model_name").click();
    await page.getByTestId("gpt-4o-1-option").click();

    await page.waitForSelector('[data-testid="float_float_temperature"]', {
      timeout: 1000,
    });

    await page.getByTestId("float_float_temperature").fill("1.0");

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 1000,
    });

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.getByTestId("output-inspection-text").first().click();

    const randomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").first().click();

    await page.waitForSelector('[data-testid="float_float_temperature"]', {
      timeout: 3000,
    });

    await page.getByTestId("float_float_temperature").fill("");
    await page.getByTestId("float_float_temperature").fill("1.2");

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 1000,
    });

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.getByTestId("output-inspection-text").first().click();

    const secondRandomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").first().click();

    await page.waitForSelector("text=OpenAI", {
      timeout: 1000,
    });

    await page.getByText("OpenAI", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 1000,
    });

    await page.getByTestId("more-options-modal").click();

    await page.waitForSelector('[data-testid="freeze-path-button"]', {
      timeout: 1000,
    });

    await page.getByTestId("freeze-path-button").click();

    await page.waitForSelector('[data-testid="icon-Snowflake"]', {
      timeout: 1000,
    });

    expect(await page.getByTestId("icon-Snowflake").count()).toBeGreaterThan(0);

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 1000,
    });

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page.getByTestId("output-inspection-text").first().click();

    const thirdRandomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").first().click();

    expect(randomTextGeneratedByAI).not.toEqual(secondRandomTextGeneratedByAI);
    expect(randomTextGeneratedByAI).not.toEqual(thirdRandomTextGeneratedByAI);
    expect(secondRandomTextGeneratedByAI).toEqual(thirdRandomTextGeneratedByAI);
  },
);
