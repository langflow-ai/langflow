import { expect, test } from "@playwright/test";

test("IntComponent", async ({ page }) => {
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
  await page.getByPlaceholder("Search").fill("getrequest");

  await page.waitForTimeout(2000);

  await page
    .getByTestId("utilitiesGET Request")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.locator('//*[@id="int-input-2"]').click();
  await page
    .locator('//*[@id="int-input-2"]')
    .fill("123456789123456789123456789");

  let value = await page.locator('//*[@id="int-input-2"]').inputValue();

  if (value != "123456789123456789123456789") {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="int-input-2"]').click();
  await page.locator('//*[@id="int-input-2"]').fill("0");

  value = await page.locator('//*[@id="int-input-2"]').inputValue();

  if (value != "0") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  value = await page.locator('//*[@id="edit-int-input-2"]').inputValue();

  if (value != "0") {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="edit-int-input-2"]').click();
  await page
    .locator('//*[@id="edit-int-input-2"]')
    .fill("123456789123456789123456789");

  await page.locator('//*[@id="showheaders"]').click();
  expect(await page.locator('//*[@id="showheaders"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showtimeout"]').click();
  expect(await page.locator('//*[@id="showtimeout"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showurl"]').click();
  expect(await page.locator('//*[@id="showurl"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showheaders"]').click();
  expect(await page.locator('//*[@id="showheaders"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showurl"]').click();
  expect(await page.locator('//*[@id="showurl"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="saveChangesBtn"]').click();

  const plusButtonLocator = page.locator('//*[@id="int-input-2"]');
  const elementCount = await plusButtonLocator.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("edit-button-modal").click();

    await page.locator('//*[@id="showtimeout"]').click();
    expect(
      await page.locator('//*[@id="showtimeout"]').isChecked()
    ).toBeTruthy();

    const valueEditNode = await page
      .locator('//*[@id="edit-int-input-2"]')
      .inputValue();

    if (valueEditNode != "123456789123456789123456789") {
      expect(false).toBeTruthy();
    }

    await page.locator('//*[@id="saveChangesBtn"]').click();
    await page.locator('//*[@id="int-input-2"]').click();
    await page.locator('//*[@id="int-input-2"]').fill("3");

    let value = await page.locator('//*[@id="int-input-2"]').inputValue();

    if (value != "3") {
      expect(false).toBeTruthy();
    }

    await page.locator('//*[@id="int-input-2"]').click();
    await page.locator('//*[@id="int-input-2"]').fill("-3");

    value = await page.locator('//*[@id="int-input-2"]').inputValue();

    if (value != "0") {
      expect(false).toBeTruthy();
    }
  }
});
