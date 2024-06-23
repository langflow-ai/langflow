import { expect, test } from "@playwright/test";

test("GlobalVariables", async ({ page }) => {
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

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(3000);
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("openai");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("modelsOpenAI")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  const genericName = Math.random().toString();
  const credentialName = Math.random().toString();

  await page.getByTestId("icon-Globe").nth(0).click();
  await page.getByText("Add New Variable", { exact: true }).click();
  await page
    .getByPlaceholder("Insert a name for the variable...")
    .fill(genericName);
  await page.getByTestId("icon-ChevronsUpDown").nth(1).click();
  await page.getByText("Generic", { exact: true }).click();
  await page
    .getByPlaceholder("Insert a value for the variable...")
    .fill("This is a test of generic variable value");
  await page.getByText("Save Variable", { exact: true }).click();
  expect(page.getByText(genericName, { exact: true })).not.toBeNull();
  await page.getByText(genericName, { exact: true }).isVisible();

  await page.getByText("Add New Variable", { exact: true }).click();
  await page
    .getByPlaceholder("Insert a name for the variable...")
    .fill(credentialName);
  await page.getByTestId("icon-ChevronsUpDown").nth(1).click();
  await page.getByText("Credential", { exact: true }).click();
  await page
    .getByPlaceholder("Insert a value for the variable...")
    .fill("This is a test of credential variable value");
  await page.getByText("Save Variable", { exact: true }).click();
  expect(page.getByText(credentialName, { exact: true })).not.toBeNull();
  await page.getByText(credentialName, { exact: true }).isVisible();
  await page.waitForTimeout(2000);

  await page
    .getByText(credentialName, { exact: true })
    .hover()
    .then(async () => {
      await page.getByTestId("icon-Trash2").last().click();
      await page.getByText("Delete", { exact: true }).nth(1).click();
    });
});
