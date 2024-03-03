import { expect, test } from "@playwright/test";

test("dropDownComponent", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("amazon");

  await page.waitForTimeout(2000);

  await page
    .getByTestId("model_specsAmazon Bedrock")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTestId("dropdown-model_id-display").click();
  await page.getByTestId("ai21.j2-grande-instruct-0-option").click();

  let value = await page.getByTestId("dropdown-model_id-display").innerText();
  if (value !== "ai21.j2-grande-instruct") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("dropdown-model_id-display").click();
  await page.getByTestId("ai21.j2-jumbo-instruct-1-option").click();

  value = await page.getByTestId("dropdown-model_id-display").innerText();
  if (value !== "ai21.j2-jumbo-instruct") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  value = await page.getByTestId("dropdown-edit-model_id-display").innerText();
  if (value !== "ai21.j2-jumbo-instruct") {
    expect(false).toBeTruthy();
  }

  // showcode
  await page.locator('//*[@id="showcode"]').click();
  expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeTruthy();

  // showmodel_id
  await page.locator('//*[@id="showmodel_id"]').click();
  expect(await page.locator('//*[@id="showmodel_id"]').isChecked()).toBeFalsy();

  // showcode
  await page.locator('//*[@id="showcode"]').click();
  expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeFalsy();

  // showmodel_id
  await page.locator('//*[@id="showmodel_id"]').click();
  expect(
    await page.locator('//*[@id="showmodel_id"]').isChecked()
  ).toBeTruthy();

  // showcode
  await page.locator('//*[@id="showcode"]').click();
  expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeTruthy();

  // showmodel_id
  await page.locator('//*[@id="showmodel_id"]').click();
  expect(await page.locator('//*[@id="showmodel_id"]').isChecked()).toBeFalsy();

  // showcode
  await page.locator('//*[@id="showcode"]').click();
  expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeFalsy();

  // showmodel_id
  await page.locator('//*[@id="showmodel_id"]').click();
  expect(
    await page.locator('//*[@id="showmodel_id"]').isChecked()
  ).toBeTruthy();

  await page.getByTestId("dropdown-edit-model_id-display").click();
  await page.getByTestId("ai21.j2-ultra-v1-5-option").click();

  value = await page.getByTestId("dropdown-edit-model_id-display").innerText();
  if (value !== "ai21.j2-ultra-v1") {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="saveChangesBtn"]').click();

  value = await page.getByTestId("dropdown-model_id-display").innerText();
  if (value !== "ai21.j2-ultra-v1") {
    expect(false).toBeTruthy();
  }
});
