import { expect, Page, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { evaluateReactStateChanges } from "../../utils/evaluate-input-react-state-changes";
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

    await page.waitForSelector('[data-testid="default_slider_display_value"]', {
      timeout: 1000,
    });

    await page.getByTestId("fit_view").click();
    await page
      .getByTestId("default_slider_display_value")
      .click({ force: true });

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 1000,
    });

    await page.getByTestId("button_run_chat output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page
      .getByTestId("output-inspection-message-chatoutput")
      .first()
      .click();

    await page.getByRole("gridcell").nth(4).click();

    const randomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").last().click();
    await page.getByText("Close").last().click();

    await page.waitForSelector('[data-testid="default_slider_display_value"]', {
      timeout: 1000,
    });

    await moveSlider(page, "right", false);

    await page.waitForSelector('[data-testid="button_run_chat output"]', {
      timeout: 1000,
    });

    await page.getByTestId("button_run_chat output").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByText("built successfully").last().click({
      timeout: 15000,
    });

    await page
      .getByTestId("output-inspection-message-chatoutput")
      .first()
      .click();

    await page.getByRole("gridcell").nth(4).click();

    const secondRandomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").last().click();
    await page.getByText("Close").last().click();

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

    await page
      .getByTestId("output-inspection-message-chatoutput")
      .first()
      .click();

    await page.getByRole("gridcell").nth(4).click();

    const thirdRandomTextGeneratedByAI = await page
      .getByPlaceholder("Empty")
      .first()
      .inputValue();

    await page.getByText("Close").last().click();
    await page.getByText("Close").last().click();

    expect(randomTextGeneratedByAI).not.toEqual(secondRandomTextGeneratedByAI);
    expect(randomTextGeneratedByAI).not.toEqual(thirdRandomTextGeneratedByAI);
    expect(secondRandomTextGeneratedByAI).toEqual(thirdRandomTextGeneratedByAI);
  },
);

async function moveSlider(
  page: Page,
  side: "left" | "right",
  advanced: boolean = false,
) {
  const thumbSelector = `slider_thumb${advanced ? "_advanced" : ""}`;
  const trackSelector = `slider_track${advanced ? "_advanced" : ""}`;

  await page.getByTestId(thumbSelector).click();

  const trackBoundingBox = await page.getByTestId(trackSelector).boundingBox();

  if (trackBoundingBox) {
    const moveDistance =
      trackBoundingBox.width * 0.1 * (side === "left" ? -1 : 1);
    const centerX = trackBoundingBox.x + trackBoundingBox.width / 2;
    const centerY = trackBoundingBox.y + trackBoundingBox.height / 2;

    await page.mouse.move(centerX + moveDistance, centerY);
    await page.mouse.down();
    await page.mouse.up();
  }
}
