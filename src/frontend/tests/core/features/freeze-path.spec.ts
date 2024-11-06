import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("user must be able to freeze a path", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }

  let filledApiKey = await page.getByTestId("remove-icon-badge").count();
  while (filledApiKey > 0) {
    await page.getByTestId("remove-icon-badge").first().click();
    await page.waitForTimeout(1000);
    filledApiKey = await page.getByTestId("remove-icon-badge").count();
  }

  const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
  const isApiKeyInputVisible = await apiKeyInput.isVisible();

  if (isApiKeyInputVisible) {
    await apiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
  }

  await page
    .getByTestId("textarea_str_input_value")
    .first()
    .fill(
      "say a random number between 1 and 100000 and a random animal that lives in the sea",
    );

  await page.getByTestId("dropdown_str_model_name").click();
  await page.getByTestId("gpt-4o-1-option").click();

  await page.waitForTimeout(1000);

  await page.getByTestId("float_float_temperature").fill("1.0");

  await page.waitForTimeout(1000);

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

  await page.waitForTimeout(3000);

  await page.getByTestId("float_float_temperature").fill("");
  await page.getByTestId("float_float_temperature").fill("1.2");

  await page.waitForTimeout(1000);

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

  await page.waitForTimeout(3000);

  await page.getByText("openai").first().click();

  await page.waitForTimeout(1000);

  await page.getByTestId("more-options-modal").click();

  await page.waitForTimeout(1000);

  await page.getByTestId("freeze-path-button").click();

  await page.waitForTimeout(1000);

  expect(await page.getByTestId("icon-Snowflake").count()).toBeGreaterThan(0);

  await page.waitForTimeout(1000);
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
});
