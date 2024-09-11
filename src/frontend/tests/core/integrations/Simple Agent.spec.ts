import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("Simple Agent", async ({ page }) => {
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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByRole("heading", { name: "Simple Agent" }).click();

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }

  await page
    .getByTestId("popover-anchor-input-api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

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

  await page.getByText("Playground", { exact: true }).click();

  await page.waitForSelector(
    "text=Use the Python REPL tool to create a python function that calculates 4 + 4 and stores it in a variable.",
    {
      timeout: 30000,
    },
  );

  await page.waitForTimeout(1000);

  expect(page.getByText("User")).toBeVisible();

  expect(page.locator(".language-python")).toBeVisible();

  let pythonWords = await page.getByText("4 + 4").count();

  expect(pythonWords).toBe(3);

  await page
    .getByPlaceholder("Send a message...")
    .fill("write short python scsript to say hello world");

  await page.getByTestId("icon-LucideSend").last().click();

  await page.waitForSelector(
    "text=write short python scsript to say hello world",
    {
      timeout: 30000,
    },
  );

  await page.waitForSelector('[data-testid="icon-Copy"]', {
    timeout: 100000,
  });

  await page.waitForTimeout(1000);

  await page.getByTestId("icon-Copy").last().click();

  await page.waitForTimeout(500);

  await page.getByPlaceholder("Send a message...").click();

  await page.waitForTimeout(500);

  await page.keyboard.press("Control+V");

  await page.waitForTimeout(500);

  pythonWords = await page.getByText("Hello, World!").count();

  expect(pythonWords).toBe(3);
});
