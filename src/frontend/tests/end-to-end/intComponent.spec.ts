import { expect, test } from "@playwright/test";

test("IntComponent", async ({ page }) => {
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
    .getByTestId("model_specsChatOpenAI")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();
  await page.getByTestId("showmax_tokens").click();

  await page.getByText("Save Changes", { exact: true }).click();
  await page.getByTestId("int-input-max_tokens").click();
  await page
    .getByTestId("int-input-max_tokens")
    .fill("123456789123456789123456789");

  let value = await page.getByTestId("int-input-max_tokens").inputValue();

  if (value != "123456789123456789123456789") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("int-input-max_tokens").click();
  await page.getByTestId("int-input-max_tokens").fill("0");

  value = await page.getByTestId("int-input-max_tokens").inputValue();

  if (value != "0") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("title-ChatOpenAI").click();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  value = await page.getByTestId("edit-int-input-max_tokens").inputValue();

  if (value != "0") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("edit-int-input-max_tokens").click();
  await page
    .getByTestId("edit-int-input-max_tokens")
    .fill("123456789123456789123456789");

  await page.locator('//*[@id="showmodel_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showmodel_kwargs"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showmodel_name"]').click();
  expect(
    await page.locator('//*[@id="showmodel_name"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showopenai_api_base"]').click();
  expect(
    await page.locator('//*[@id="showopenai_api_base"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showopenai_api_key"]').click();
  expect(
    await page.locator('//*[@id="showopenai_api_key"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showtemperature"]').click();
  expect(
    await page.locator('//*[@id="showtemperature"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showmodel_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showmodel_kwargs"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showmodel_name"]').click();
  expect(
    await page.locator('//*[@id="showmodel_name"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showopenai_api_base"]').click();
  expect(
    await page.locator('//*[@id="showopenai_api_base"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showopenai_api_key"]').click();
  expect(
    await page.locator('//*[@id="showopenai_api_key"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showtemperature"]').click();
  expect(
    await page.locator('//*[@id="showtemperature"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showmodel_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showmodel_kwargs"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showmodel_name"]').click();
  expect(
    await page.locator('//*[@id="showmodel_name"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showopenai_api_base"]').click();
  expect(
    await page.locator('//*[@id="showopenai_api_base"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showopenai_api_key"]').click();
  expect(
    await page.locator('//*[@id="showopenai_api_key"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showtemperature"]').click();
  expect(
    await page.locator('//*[@id="showtemperature"]').isChecked()
  ).toBeFalsy();

  await page.getByText("Save Changes", { exact: true }).click();

  const plusButtonLocator = page.getByTestId("int-input-max_tokens");
  const elementCount = await plusButtonLocator?.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("edit-button-modal").click();

    await page.locator('//*[@id="showtimeout"]').click();
    expect(
      await page.locator('//*[@id="showtimeout"]').isChecked()
    ).toBeTruthy();

    const valueEditNode = await page
      .getByTestId("edit-int-input-max_tokens")
      .inputValue();

    if (valueEditNode != "123456789123456789123456789") {
      expect(false).toBeTruthy();
    }

    await page.getByText("Save Changes", { exact: true }).click();
    await page.getByTestId("int-input-max_tokens").click();
    await page.getByTestId("int-input-max_tokens").fill("3");

    let value = await page.getByTestId("int-input-max_tokens").inputValue();

    if (value != "3") {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("int-input-max_tokens").click();
    await page.getByTestId("int-input-max_tokens").fill("-3");

    value = await page.getByTestId("int-input-max_tokens").inputValue();

    if (value != "0") {
      expect(false).toBeTruthy();
    }
  }
});
