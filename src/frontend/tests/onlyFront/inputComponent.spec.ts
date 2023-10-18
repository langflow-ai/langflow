import { expect, test } from "@playwright/test";

test("InputComponent", async ({ page }) => {
  await page.routeFromHAR("harFiles/langflow.har", {
    url: "**/api/v1/**",
    update: false,
  });
  await page.route("**/api/v1/flows/", async (route) => {
    const json = {
      id: "e9ac1bdc-429b-475d-ac03-d26f9a2a3210",
    };
    await route.fulfill({ json, status: 201 });
  });
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("Chroma");

  await page.waitForTimeout(2000);

  await page
    .locator('//*[@id="sideChroma"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.locator("#input-8").click();
  await page
    .locator("#input-8")
    .fill("collection_name_test_123123123!@#$&*(&%$@");

  let value = await page.locator("#input-8").inputValue();

  if (value != "collection_name_test_123123123!@#$&*(&%$@") {
    expect(false).toBeTruthy();
  }

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div[1]/div/div[2]/div/div/div[1]/div/div[1]/div'
    )
    .click();
  await page.locator('//*[@id="editAdvancedIcon"]').click();

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

  await page.locator('//*[@id="showchroma_server_http_port"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_http_port"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showchroma_server_ssl_enabled"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_ssl_enabled"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showcollection_name"]').click();
  expect(
    await page.locator('//*[@id="showcollection_name"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showpersist"]').click();
  expect(await page.locator('//*[@id="showpersist"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showpersist_directory"]').click();
  expect(
    await page.locator('//*[@id="showpersist_directory"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showsearch_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showsearch_kwargs"]').isChecked()
  ).toBeTruthy();

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

  await page.locator('//*[@id="showchroma_server_http_port"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_http_port"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showchroma_server_ssl_enabled"]').click();
  expect(
    await page.locator('//*[@id="showchroma_server_ssl_enabled"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showpersist"]').click();
  expect(await page.locator('//*[@id="showpersist"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showpersist_directory"]').click();
  expect(
    await page.locator('//*[@id="showpersist_directory"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showsearch_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showsearch_kwargs"]').isChecked()
  ).toBeFalsy();

  let valueEditNode = await page.locator('//*[@id="input-5"]').inputValue();

  if (valueEditNode != "collection_name_test_123123123!@#$&*(&%$@") {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="input-5"]').click();
  await page
    .locator('//*[@id="input-5"]')
    .fill("NEW_collection_name_test_123123123!@#$&*(&%$@");

  await page.locator('//*[@id="saveChangesBtn"]').click();

  const plusButtonLocator = page.locator("#input-8");
  const elementCount = await plusButtonLocator.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page
      .locator(
        '//*[@id="react-flow-id"]/div[1]/div[1]/div[1]/div/div[2]/div/div/div[1]/div/div[1]/div'
      )
      .click();
    await page.locator('//*[@id="editAdvancedIcon"]').click();

    await page.locator('//*[@id="showcollection_name"]').click();
    expect(
      await page.locator('//*[@id="showcollection_name"]').isChecked()
    ).toBeTruthy();

    await page.locator('//*[@id="saveChangesBtn"]').click();

    let value = await page.locator("#input-8").inputValue();

    if (value != "NEW_collection_name_test_123123123!@#$&*(&%$@") {
      expect(false).toBeTruthy();
    }
  }
});
