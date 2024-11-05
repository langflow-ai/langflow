import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import uaParser from "ua-parser-js";

test.skip("Simple Agent", async ({ page }) => {
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

  const getUA = await page.evaluate(() => navigator.userAgent);
  const userAgentInfo = uaParser(getUA);
  let control = "Control";

  if (userAgentInfo.os.name.includes("Mac")) {
    control = "Meta";
  }

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Simple Agent" }).first().click();

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

  await page
    .getByTestId("popover-anchor-input-api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByTestId("fit_view").click();

  await page.getByTestId("dropdown_str_model_name").click();
  await page.getByTestId("gpt-4o-1-option").click();

  await page.waitForTimeout(1000);

  await page
    .getByTestId("textarea_str_input_value")
    .fill(
      "Use the Python REPL tool to create a python function that calculates 4 + 4 and stores it in a variable.",
    );

  await page.getByTestId("button_run_chat output").click();
  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByText("Playground", { exact: true }).last().click();

  await page.waitForSelector(
    "text=Use the Python REPL tool to create a python function that calculates 4 + 4 and stores it in a variable.",
    {
      timeout: 30000,
    },
  );

  await page.waitForTimeout(1000);

  expect(page.getByText("User")).toBeVisible();

  let pythonWords = await page.getByText("4 + 4").count();

  expect(pythonWords).toBe(2);

  await page
    .getByPlaceholder("Send a message...")
    .fill("write short python script to say hello world");

  await page.getByTestId("button-send").last().click();

  await page.waitForSelector(
    "text=write short python script to say hello world",
    {
      timeout: 30000,
    },
  );

  await page.waitForSelector('[data-testid="copy-code-button"]', {
    timeout: 100000,
    state: "visible",
  });

  await page.waitForTimeout(1000);

  await page.getByTestId("copy-code-button").last().click();

  await page.waitForTimeout(500);

  await page.getByPlaceholder("Send a message...").click();

  await page.waitForTimeout(500);

  await page.keyboard.press(`${control}+V`);

  await page.waitForTimeout(500);

  pythonWords = await page.getByText("print(").count();

  expect(pythonWords).toBe(1);
});
