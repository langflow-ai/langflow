import { expect, test } from "@playwright/test";

test("should share component with share button", async ({ page }) => {
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
  await page.waitForTimeout(1000);

  const randomName = Math.random().toString(36).substring(2);

  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForTimeout(1000);
  const flowName = await page.getByTestId("flow_name").innerText();
  await page.getByTestId("flow_name").click();
  await page.getByText("Settings").click();
  const flowDescription = await page
    .getByPlaceholder("Flow description")
    .inputValue();
  await page.getByPlaceholder("Flow name").fill(randomName);
  await page.getByText("Save").last().click();
  await page.getByText("Close").last().click();

  await page.waitForSelector('[data-testid="shared-button-flow"]', {
    timeout: 100000,
  });

  await page.getByTestId("shared-button-flow").first().click();
  await page.getByText("Name:").isVisible();
  await page.getByText("Description:").isVisible();
  await page.getByText("Set workflow status to public").isVisible();
  await page
    .getByText(
      "Attention: API keys in specified fields are automatically removed upon sharing.",
    )
    .isVisible();
  await page.getByText("Export").first().isVisible();
  await page.getByText("Share Flow").first().isVisible();

  await page.waitForTimeout(5000);

  await page.getByText("Agent").first().isVisible();
  await page.getByText("Memory").first().isVisible();
  await page.getByText("Chain").first().isVisible();
  await page.getByText("Vector Store").first().isVisible();
  await page.getByText("Prompt").last().isVisible();
  await page.getByTestId("public-checkbox").isChecked();
  await page.getByText(flowName).last().isVisible();
  await page.getByText(flowDescription).last().isVisible();
  await page.waitForTimeout(1000);
  await page.getByText("Flow shared successfully").last().isVisible();
});

test("should order the visualization", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByText("Basic RAG").isVisible();

  await page.getByTestId("select-order-store").click();
  await page.waitForTimeout(2000);
  await page.getByText("Alphabetical").click();

  await page.getByText("Album Cover Builder").isVisible();

  await page.getByTestId("select-order-store").click();
  await page.getByText("Popular").click();

  await page.getByText("Basic RAG").isVisible();
});

test("should filter by type", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByText("Website Content QA").isVisible();

  await page.getByTestId("flows-button-store").click();
  await page.waitForTimeout(8000);

  let iconGroup = await page.getByTestId("icon-Group")?.count();
  expect(iconGroup).not.toBe(0);

  await page.getByText("icon-ToyBrick").last().isHidden();

  await page.getByTestId("components-button-store").click();
  await page.waitForTimeout(8000);

  await page.getByTestId("icon-Group").last().isHidden();
  let toyBrick = await page.getByTestId("icon-ToyBrick")?.count();
  expect(toyBrick).not.toBe(0);

  await page.getByTestId("all-button-store").click();
  await page.waitForTimeout(8000);

  let iconGroupAllCount = await page.getByTestId("icon-Group")?.count();
  await page.waitForTimeout(2000);
  let toyBrickAllCount = await page.getByTestId("icon-ToyBrick")?.count();
  await page.waitForTimeout(2000);

  if (iconGroupAllCount === 0 || toyBrickAllCount === 0) {
    expect(false).toBe(true);
  }
});
