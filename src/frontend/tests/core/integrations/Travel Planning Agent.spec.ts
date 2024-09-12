import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("Travel Planning Agent", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  test.skip(
    !process?.env?.SEARCH_API_KEY,
    "SEARCH_API_KEY required to run this test",
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

  await page.getByRole("heading", { name: "Travel Planning Agents" }).click();

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
    .last()
    .fill(process.env.SEARCH_API_KEY ?? "");

  await page
    .getByTestId("popover-anchor-input-api_key")
    .first()
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByTestId("dropdown_str_model_name").click();
  await page.getByTestId("gpt-4o-1-option").click();

  await page.waitForTimeout(1000);

  await page.getByTestId("button_run_chat output").click();
  await page.waitForSelector("text=built successfully", { timeout: 60000 * 3 });

  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });
  await page.getByText("Playground", { exact: true }).click();

  await page.waitForSelector("text=default session", {
    timeout: 30000,
  });

  await page.waitForTimeout(1000);

  const output = await page.getByTestId("div-chat-message").allTextContents();
  const outputText = output.join("\n");

  expect(outputText.toLowerCase()).toContain("weather");
  expect(outputText.toLowerCase()).toContain("budget");

  expect(outputText.toLowerCase()).toContain("uberlândia");
  expect(outputText.toLowerCase()).toContain("pão de queijo");
});
