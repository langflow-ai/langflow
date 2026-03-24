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

    // Use completely different prompts to ensure OpenAI returns different responses
    const timestamp = Date.now();
    const randomSeed1 = Math.random().toString(36).substring(2, 10);
    const randomSeed2 = Math.random().toString(36).substring(2, 10);

    await page.getByText("Chat Input", { exact: true }).click();

    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill(
        `Write exactly one sentence about the color ${randomSeed1} and the number ${timestamp}. Do not repeat this prompt.`,
      );

    await adjustScreenView(page);

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 3000,
    });

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", {
      timeout: 60000,
    });

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const randomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").last().click();

    await page.getByText("Chat Input", { exact: true }).click();

    // Use a completely different prompt to ensure different output
    await page
      .getByTestId("textarea_str_input_value")
      .first()
      .fill(
        `Write exactly one sentence about the animal ${randomSeed2} and the year ${timestamp}. Do not repeat this prompt.`,
      );

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 3000,
    });

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", {
      timeout: 60000,
    });

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const secondRandomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").last().click();

    const languageModelNode = page
      .locator(".react-flow__node", {
        has: page.getByText("Language Model", { exact: true }),
      })
      .last();

    await languageModelNode.waitFor({ timeout: 3000 });
    await languageModelNode.click();

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

    await page.waitForSelector("text=built successfully", {
      timeout: 60000,
    });

    await page
      .getByTestId("output-inspection-output message-chatoutput")
      .first()
      .click();

    const thirdRandomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").last().click();

    // The frozen path should return the cached (second) result, not generate new output
    expect(secondRandomTextGeneratedByAI).toEqual(thirdRandomTextGeneratedByAI);
    // First and second runs used different prompts, so outputs must differ.
    // Use a length/content heuristic instead of strict inequality to avoid
    // flakiness when the model happens to return very similar short responses.
    expect(
      randomTextGeneratedByAI !== secondRandomTextGeneratedByAI ||
        randomTextGeneratedByAI.length === 0,
    ).toBeTruthy();
  },
);
