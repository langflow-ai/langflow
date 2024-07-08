import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("Blog Writer", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
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

  await page.getByRole("heading", { name: "Blog Writer" }).click();
  await page.waitForTimeout(1000);

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
  await page
    .getByTestId("input-list-input_urls-0")
    .nth(0)
    .fill(
      "https://www.natgeokids.com/uk/discover/animals/sea-life/turtle-facts/",
    );
  await page
    .getByTestId("input-list-input_urls-1")
    .nth(0)
    .fill("https://www.originaldiving.com/blog/top-ten-turtle-facts");

  await page
    .getByTestId("popover-anchor-input-input_value")
    .nth(0)
    .fill(
      "Use the references above for style to write a new blog/tutorial about turtles. Suggest non-covered topics.",
    );

  await page.getByTestId("button_run_chat output").click();
  await page.waitForTimeout(5000);

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.getByText("built successfully").last().click({
    timeout: 30000,
  });

  await page.getByText("Playground", { exact: true }).click();
  await page
    .getByPlaceholder(
      "No chat input variables found. Click to run your flow.",
      { exact: true },
    )
    .last()
    .isVisible();

  await page.waitForTimeout(3000);

  await page.getByText("turtles").last().isVisible();
  await page.getByText("sea").last().isVisible();
  await page.getByText("survival").last().isVisible();

  await page.getByText("Instructions").last().click();

  const value = await page
    .getByPlaceholder("Enter text...")
    .last()
    .inputValue();

  expect(value).toBe(
    "Use the references above for style to write a new blog/tutorial about turtles. Suggest non-covered topics.",
  );

  await page.getByTestId("icon-ExternalLink").last().click();

  const count = await page
    .getByText(
      "Use the references above for style to write a new blog/tutorial about turtles. Suggest non-covered topics.",
    )
    .count();

  if (count <= 1) {
    expect(false).toBe(true);
  }
});
