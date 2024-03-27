import { expect, test } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  // await page.waitForTimeout(12000);
  // test.setTimeout(120000);
});
test("NestedComponent", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(1000);

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(1000);

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

  //showpool_threads
  await page.locator('//*[@id="showpool_threads"]').click();

  expect(
    await page.locator('//*[@id="showpool_threads"]').isChecked()
  ).toBeTruthy();

  //showtext_key
  await page.locator('//*[@id="showtext_key"]').click();

  expect(await page.locator('//*[@id="showtext_key"]').isChecked()).toBeFalsy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked()
  ).toBeFalsy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked()
  ).toBeFalsy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked()
  ).toBeFalsy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeFalsy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked()
  ).toBeTruthy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked()
  ).toBeTruthy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked()
  ).toBeTruthy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeTruthy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked()
  ).toBeFalsy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked()
  ).toBeFalsy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked()
  ).toBeFalsy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeFalsy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked()
  ).toBeTruthy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked()
  ).toBeTruthy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked()
  ).toBeTruthy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeTruthy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked()
  ).toBeFalsy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked()
  ).toBeFalsy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked()
  ).toBeFalsy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeFalsy();

  // showindex_name
  await page.locator('//*[@id="showindex_name"]').click();

  expect(
    await page.locator('//*[@id="showindex_name"]').isChecked()
  ).toBeTruthy();

  // shownamespace
  await page.locator('//*[@id="shownamespace"]').click();

  expect(
    await page.locator('//*[@id="shownamespace"]').isChecked()
  ).toBeTruthy();

  // showpinecone_api_key
  await page.locator('//*[@id="showpinecone_api_key"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_api_key"]').isChecked()
  ).toBeTruthy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeTruthy();

  //showpool_threads
  await page.locator('//*[@id="showpool_threads"]').click();

  expect(
    await page.locator('//*[@id="showpool_threads"]').isChecked()
  ).toBeFalsy();

  //showtext_key
  await page.locator('//*[@id="showtext_key"]').click();

  expect(
    await page.locator('//*[@id="showtext_key"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="saveChangesBtn"]').click();
});
