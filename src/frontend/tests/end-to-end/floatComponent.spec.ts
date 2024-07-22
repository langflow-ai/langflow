import { expect, test } from "@playwright/test";

test("FloatComponent", async ({ page }) => {
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
  await page.getByPlaceholder("Search").fill("ollama");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("modelsOllama")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page.waitForTimeout(2000);
  await page.locator('//*[@id="float-input"]').click();
  await page.locator('//*[@id="float-input"]').fill("");
  await page.waitForTimeout(2000);
  await page.locator('//*[@id="float-input"]').fill("3");

  let value = await page.locator('//*[@id="float-input"]').inputValue();

  if (value != "2") {
    expect(false).toBeTruthy();
  }

  await page.waitForTimeout(2000);
  await page.locator('//*[@id="float-input"]').click();
  await page.locator('//*[@id="float-input"]').fill("");
  await page.waitForTimeout(2000);
  await page.locator('//*[@id="float-input"]').fill("-3");

  value = await page.locator('//*[@id="float-input"]').inputValue();

  if (value != "-2") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  await page.getByTestId("showmirostat_eta").click();
  expect(
    await page.locator('//*[@id="showmirostat_eta"]').isChecked(),
  ).toBeTruthy();

  await page.getByTestId("showmirostat_eta").click();
  expect(
    await page.locator('//*[@id="showmirostat_eta"]').isChecked(),
  ).toBeFalsy();

  await page.getByTestId("showmirostat_eta").click();
  expect(
    await page.locator('//*[@id="showmirostat_eta"]').isChecked(),
  ).toBeTruthy();

  await page.getByTestId("showmirostat_eta").click();
  expect(
    await page.locator('//*[@id="showmirostat_eta"]').isChecked(),
  ).toBeFalsy();

  await page.getByTestId("showmirostat_tau").click();
  expect(
    await page.locator('//*[@id="showmirostat_tau"]').isChecked(),
  ).toBeTruthy();

  await page.getByTestId("showmirostat_tau").click();
  expect(
    await page.locator('//*[@id="showmirostat_tau"]').isChecked(),
  ).toBeFalsy();

  await page.getByText("Close").last().click();

  const plusButtonLocator = page.locator('//*[@id="float-input"]');
  const elementCount = await plusButtonLocator?.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("edit-button-modal").click();

    // showtemperature
    await page.locator('//*[@id="showtemperature"]').click();
    expect(
      await page.locator('//*[@id="showtemperature"]').isChecked(),
    ).toBeTruthy();

    await page.getByText("Close").last().click();
    await page.locator('//*[@id="float-input"]').click();
    await page.locator('//*[@id="float-input"]').fill("3");

    let value = await page.locator('//*[@id="float-input"]').inputValue();

    if (value != "1") {
      expect(false).toBeTruthy();
    }

    await page.locator('//*[@id="float-input"]').click();
    await page.locator('//*[@id="float-input"]').fill("-3");

    value = await page.locator('//*[@id="float-input"]').inputValue();

    if (value != "-1") {
      expect(false).toBeTruthy();
    }
  }
});
