import { expect, test } from "@playwright/test";

test("NestedComponent", async ({ page }) => {
  await page.routeFromHAR("harFiles/backend_12112023.har", {
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
  await page.getByPlaceholder("Search").fill("pinecone");

  await page.waitForTimeout(2000);

  await page
    .getByTestId("vectorstoresPinecone")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

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
  ).toBeTruthy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeTruthy();

  // showsearch_kwargs
  await page.locator('//*[@id="showsearch_kwargs"]').click();

  expect(
    await page.locator('//*[@id="showsearch_kwargs"]').isChecked()
  ).toBeTruthy();

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
  ).toBeFalsy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeFalsy();

  // showsearch_kwargs
  await page.locator('//*[@id="showsearch_kwargs"]').click();

  expect(
    await page.locator('//*[@id="showsearch_kwargs"]').isChecked()
  ).toBeFalsy();

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
  ).toBeTruthy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeTruthy();

  // showsearch_kwargs
  await page.locator('//*[@id="showsearch_kwargs"]').click();

  expect(
    await page.locator('//*[@id="showsearch_kwargs"]').isChecked()
  ).toBeTruthy();

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
  ).toBeFalsy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeFalsy();

  // showsearch_kwargs
  await page.locator('//*[@id="showsearch_kwargs"]').click();

  expect(
    await page.locator('//*[@id="showsearch_kwargs"]').isChecked()
  ).toBeFalsy();

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
  ).toBeTruthy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeTruthy();

  // showsearch_kwargs
  await page.locator('//*[@id="showsearch_kwargs"]').click();

  expect(
    await page.locator('//*[@id="showsearch_kwargs"]').isChecked()
  ).toBeTruthy();

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
  ).toBeFalsy();

  // showpinecone_env
  await page.locator('//*[@id="showpinecone_env"]').click();

  expect(
    await page.locator('//*[@id="showpinecone_env"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="saveChangesBtn"]').click();

  await page.getByTestId("div-dict-input").click();
});
