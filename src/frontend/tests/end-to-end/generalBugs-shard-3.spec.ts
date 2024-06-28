import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("should delete rows from table message", async ({ page }) => {
  if (!process?.env?.OPENAI_API_KEY) {
    //You must set the OPENAI_API_KEY on .env file to run this test
    expect(false).toBe(true);
  }

  await page.goto("/");
  await page.waitForTimeout(2000);

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

  await page.getByTestId("button_run_chat output").click();
  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByText("Playground", { exact: true }).click();
  await page
    .getByText("No input message provided.", { exact: true })
    .last()
    .isVisible();

  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });

  await page
    .getByTestId("input-chat-playground")
    .last()
    .fill("Say hello as a pirate");
  await page.getByTestId("icon-LucideSend").last().click();

  await page.waitForSelector("text=matey", {
    timeout: 100000,
  });

  await page.getByText("Close").last().click();
  await page.getByTestId("user-profile-settings").last().click();
  await page.getByText("Settings").last().click();
  await page.getByText("Messages").last().click();

  const label = "Press Space to toggle all rows selection (unchecked)";
  await page.getByLabel(label).first().click();

  await page.getByTestId("icon-Trash2").first().click();

  await page.waitForSelector("text=No Data Available", { timeout: 30000 });
  await page.getByText("No Data Available").isVisible();
});
