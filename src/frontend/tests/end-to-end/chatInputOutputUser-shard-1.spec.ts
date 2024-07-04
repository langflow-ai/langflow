import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";

test("user must be able to see output inspection", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

  await page.goto("/");

  await page.waitForTimeout(1000);

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
    await page.waitForTimeout(5000);
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

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByTestId("dropdown-model_name").click();
  await page.getByTestId("gpt-4o-0-option").click();

  await page.waitForTimeout(2000);
  await page.getByTestId("button_run_chat output").last().click();

  await page.waitForTimeout(5000);

  await page.waitForSelector('[data-testid="icon-ScanEye"]', {
    timeout: 30000,
  });

  await page.getByTestId("icon-ScanEye").nth(4).click();

  await page.getByText("Sender", { exact: true }).isVisible();
  await page.getByText("Type", { exact: true }).isVisible();
  await page.getByText("User", { exact: true }).last().isVisible();
});
