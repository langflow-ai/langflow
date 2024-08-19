import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("erase button should clear the chat messages", async ({ page }) => {
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
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForTimeout(1000);

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
  await page.getByText("Playground", { exact: true }).click();

  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });

  await page.getByTestId("input-chat-playground").fill("Hello, how are you?");

  await page.waitForSelector('[data-testid="icon-LucideSend"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-LucideSend").click();
  let valueUser = await page.getByTestId("sender_name_user").textContent();

  await page.waitForSelector('[data-testid="sender_name_ai"]', {
    timeout: 30000,
  });

  let valueAI = await page.getByTestId("sender_name_ai").textContent();

  expect(valueUser).toBe("User");
  expect(valueAI).toBe("AI");

  await page.getByTestId("icon-Eraser").last().click();

  await page.getByText("Hello, how are you?").isHidden();
  await page.getByText("AI", { exact: true }).last().isHidden();
  await page.getByText("User", { exact: true }).last().isHidden();
  await page.getByText("Start a conversation").isVisible();
  await page.getByText("Langflow Chat").isVisible();

  await page.waitForTimeout(1000);
  await page.getByPlaceholder("Send a message...").fill("My name is John");

  await page.waitForSelector('[data-testid="icon-LucideSend"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-LucideSend").click();

  await page.waitForSelector("text=AI", { timeout: 30000 });

  await page.getByText("Hello, how are you?").isHidden();
});
