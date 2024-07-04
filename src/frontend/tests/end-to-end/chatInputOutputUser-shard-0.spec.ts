import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";

test("user must be able to send an image on chat", async ({ page }) => {
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

  await page.waitForSelector("text=Chat Input", { timeout: 30000 });

  await page.getByText("Chat Input", { exact: true }).click();
  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();
  await page.getByText("Close").last().click();

  await page.getByText("Playground", { exact: true }).click();

  // Read the image file as a binary string
  const filePath = "tests/end-to-end/assets/chain.png";
  const fileContent = readFileSync(filePath, "base64");

  // Create the DataTransfer and File objects within the browser context
  const dataTransfer = await page.evaluateHandle(
    ({ fileContent }) => {
      const dt = new DataTransfer();
      const byteCharacters = atob(fileContent);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const file = new File([byteArray], "chain.png", { type: "image/png" });
      dt.items.add(file);
      return dt;
    },
    { fileContent },
  );

  await page.waitForSelector('[data-testid="input-chat-playground"]', {
    timeout: 100000,
  });

  // Locate the target element
  const element = await page.getByTestId("input-chat-playground");

  // Dispatch the drop event on the target element
  await element.dispatchEvent("drop", { dataTransfer });

  await page.waitForSelector('[data-testid="icon-LucideSend"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-LucideSend").click();

  await page.waitForSelector("text=chain.png", { timeout: 30000 });

  await page.getByText("chain.png").isVisible();

  await page.getByText("Close", { exact: true }).click();

  await page.waitForSelector('[data-testid="icon-ScanEye"]', {
    timeout: 30000,
  });

  await page.getByTestId("icon-ScanEye").nth(4).click();

  await page.getByText("Restart").isHidden();
});
