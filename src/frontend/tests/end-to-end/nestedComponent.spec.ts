import { expect, test } from "@playwright/test";

test("NestedComponent", async ({ page }) => {
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
  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });
  await page.getByTestId("blank-flow").click();
  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("pinecone");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("vectorstoresPinecone")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.click('//*[@id="react-flow-id"]');

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked(),
  ).toBeFalsy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked(),
  ).toBeFalsy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked(),
  ).toBeFalsy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked(),
  ).toBeTruthy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked(),
  ).toBeTruthy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked(),
  ).toBeTruthy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked(),
  ).toBeFalsy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked(),
  ).toBeFalsy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked(),
  ).toBeFalsy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked(),
  ).toBeTruthy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked(),
  ).toBeTruthy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked(),
  ).toBeTruthy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked(),
  ).toBeFalsy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked(),
  ).toBeFalsy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked(),
  ).toBeFalsy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked(),
  ).toBeTruthy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked(),
  ).toBeTruthy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked(),
  ).toBeTruthy();

  //showtext_key
  await page.locator('//*[@id="showtext_key"]').click();

  expect(
    await page.locator('//*[@id="showtext_key"]').isChecked(),
  ).toBeTruthy();

  await page.getByText("Close").last().click();
});
