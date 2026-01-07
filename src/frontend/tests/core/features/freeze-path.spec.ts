import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { addFlowToTestOnEmptyLangflow } from "../../utils/add-flow-to-test-on-empty-langflow";
import { adjustScreenView } from "../../utils/adjust-screen-view";
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

    const firstRunLangflow = await page
      .getByTestId("empty-project-description")
      .count();

    if (firstRunLangflow > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await initialGPTsetup(page);

    // Use unique prompts to avoid OpenAI caching returning identical responses
    const timestamp = Date.now();
    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill(
        `say a random number between 1 and 300000 and a random animal that lives in the sea. Request ID: ${timestamp}-1`,
      );

    await adjustScreenView(page);

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 3000,
    });

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const randomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").last().click();

    // Change the prompt to ensure different output (avoid OpenAI caching)
    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill(
        `say a random number between 1 and 300000 and a random animal that lives in the sea. Request ID: ${timestamp}-2`,
      );

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 3000,
    });

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const secondRandomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").last().click();

    await page.waitForSelector("text=OpenAI", {
      timeout: 3000,
    });

    await page.getByText("Language Model", { exact: true }).last().click();

    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 3000,
    });

    await page.getByText("Freeze").first().click();

    await page.waitForTimeout(2000);

    await page.waitForSelector('[data-testid="icon-Snowflake"]', {
      timeout: 3000,
    });

    expect(await page.getByTestId("icon-Snowflake").count()).toBeGreaterThan(0);

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 3000,
    });

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const thirdRandomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").last().click();

    expect(randomTextGeneratedByAI).not.toEqual(secondRandomTextGeneratedByAI);
    expect(randomTextGeneratedByAI).not.toEqual(thirdRandomTextGeneratedByAI);
    expect(secondRandomTextGeneratedByAI).toEqual(thirdRandomTextGeneratedByAI);
  },
);
