import { test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("should delete rows from table message", async ({ page }) => {
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

  await page.getByRole("heading", { name: "Basic Prompting" }).click();
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

  await page.getByTestId("button_run_chat output").click();
  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 30000,
  });

  await page.waitForTimeout(2000);

  await page.getByTestId("user-profile-settings").last().click();
  await page.waitForSelector(
    '[data-testid="user-profile-settings"]:last-child',
  );

  await page.waitForTimeout(500);

  await page.waitForSelector('text="Settings"');
  await page.getByText("Settings").last().click();

  await page.waitForSelector('text="Messages"');
  await page.getByText("Messages").last().click();

  await page.waitForSelector(".ag-checkbox-input");
  await page.locator(".ag-checkbox-input").first().click();

  await page.waitForTimeout(500);

  await page.waitForSelector('[data-testid="icon-Trash2"]:first-child');
  await page.getByTestId("icon-Trash2").first().click();

  await page.waitForTimeout(500);

  await page.waitForSelector("text=No Data Available", { timeout: 30000 });
  await page.getByText("No Data Available").isVisible();
});
