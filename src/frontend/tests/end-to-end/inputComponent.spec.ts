import { expect, test } from "@playwright/test";

test("InputComponent", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("Chroma");

  await page.waitForTimeout(2000);

  await page
    .getByTestId("vectorstoresChroma")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTestId("input-collection_name").click();
  await page
    .getByTestId("input-collection_name")
    .fill("collection_name_test_123123123!@#$&*(&%$@");

  let value = await page.getByTestId("input-collection_name").inputValue();

  if (value != "collection_name_test_123123123!@#$&*(&%$@") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("div-generic-node").click();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  await page.locator('//*[@id="showchroma_server_cors_allow_origins"]').click();
  expect(
    await page
      .locator('//*[@id="showchroma_server_cors_allow_origins"]')
      .isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showchroma_server_grpc_port"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_grpc_port"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showchroma_server_host"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_host"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showchroma_server_port"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_port"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showchroma_server_ssl_enabled"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_ssl_enabled"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showcollection_name"]').click();
  expect(
    await page.locator('//*[@id="showcollection_name"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showindex_directory"]').click();
  expect(
    await page.locator('//*[@id="showindex_directory"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showchroma_server_cors_allow_origins"]').click();
  expect(
    await page
      .locator('//*[@id="showchroma_server_cors_allow_origins"]')
      .isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showchroma_server_grpc_port"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_grpc_port"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showchroma_server_host"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_host"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showchroma_server_port"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_port"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showchroma_server_ssl_enabled"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_ssl_enabled"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showindex_directory"]').click();
  expect(
    await page.locator('//*[@id="showindex_directory"]').isChecked()
  ).toBeTruthy();

  let valueEditNode = await page
    .getByTestId("input-collection_name-edit")
    .inputValue();

  if (valueEditNode != "collection_name_test_123123123!@#$&*(&%$@") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("input-collection_name-edit").click();
  await page
    .getByTestId("input-collection_name-edit")
    .fill("NEW_collection_name_test_123123123!@#$&*(&%$@");

  await page.locator('//*[@id="saveChangesBtn"]').click();

  const plusButtonLocator = page.getByTestId("input-collection_name");
  const elementCount = await plusButtonLocator.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("edit-button-modal").click();

    await page.locator('//*[@id="showcollection_name"]').click();
    expect(
      await page.locator('//*[@id="showcollection_name"]').isChecked()
    ).toBeTruthy();

    await page.locator('//*[@id="saveChangesBtn"]').click();

    let value = await page.getByTestId("input-collection_name").inputValue();

    if (value != "NEW_collection_name_test_123123123!@#$&*(&%$@") {
      expect(false).toBeTruthy();
    }
  }
});
