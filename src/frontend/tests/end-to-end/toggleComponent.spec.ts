import { expect, test } from "@playwright/test";

test("ToggleComponent", async ({ page }) => {
  await page.goto("http:localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(1000);

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(1000);
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("directoryLoader");

  await page.waitForTimeout(1000);
  await page
    .getByTestId("documentloadersDirectoryLoader")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page
    .locator('//*[@id="react-flow-id"]/div[1]/div[2]/button[2]')
    .click();

  await page
    .locator('//*[@id="react-flow-id"]/div[1]/div[2]/button[2]')
    .click();

  await page
    .locator('//*[@id="react-flow-id"]/div[1]/div[2]/button[2]')
    .click();

  await page.getByTestId("div-generic-node").click();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  await page.locator('//*[@id="showload_hidden"]').click();
  expect(
    await page.locator('//*[@id="showload_hidden"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="saveChangesBtn"]').click();

  await page.getByTestId("toggle-load_hidden").click();
  expect(await page.getByTestId("toggle-load_hidden").isChecked()).toBeFalsy();

  await page.getByTestId("toggle-load_hidden").click();
  expect(await page.getByTestId("toggle-load_hidden").isChecked()).toBeTruthy();

  await page.getByTestId("toggle-load_hidden").click();
  expect(await page.getByTestId("toggle-load_hidden").isChecked()).toBeFalsy();

  await page.getByTestId("toggle-load_hidden").click();
  expect(await page.getByTestId("toggle-load_hidden").isChecked()).toBeTruthy();

  await page.getByTestId("toggle-load_hidden").click();
  expect(await page.getByTestId("toggle-load_hidden").isChecked()).toBeFalsy();

  await page.getByTestId("div-generic-node").click();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  expect(await page.getByTestId("toggle-load_hidden").isChecked()).toBeFalsy();

  await page.locator('//*[@id="showglob"]').click();
  expect(await page.locator('//*[@id="showglob"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showload_hidden"]').click();
  expect(
    await page.locator('//*[@id="showload_hidden"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showmax_concurrency"]').click();
  expect(
    await page.locator('//*[@id="showmax_concurrency"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showmetadata"]').click();
  expect(await page.locator('//*[@id="showmetadata"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showpath"]').click();
  expect(await page.locator('//*[@id="showpath"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showrecursive"]').click();
  expect(
    await page.locator('//*[@id="showrecursive"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showsilent_errors"]').click();
  expect(
    await page.locator('//*[@id="showsilent_errors"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showuse_multithreading"]').click();
  expect(
    await page.locator('//*[@id="showuse_multithreading"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showglob"]').click();
  expect(await page.locator('//*[@id="showglob"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showmax_concurrency"]').click();
  expect(
    await page.locator('//*[@id="showmax_concurrency"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showmetadata"]').click();
  expect(
    await page.locator('//*[@id="showmetadata"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showpath"]').click();
  expect(await page.locator('//*[@id="showpath"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showrecursive"]').click();
  expect(
    await page.locator('//*[@id="showrecursive"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showsilent_errors"]').click();
  expect(
    await page.locator('//*[@id="showsilent_errors"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showuse_multithreading"]').click();
  expect(
    await page.locator('//*[@id="showuse_multithreading"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="saveChangesBtn"]').click();

  const plusButtonLocator = page.getByTestId("toggle-load_hidden");
  const elementCount = await plusButtonLocator.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("edit-button-modal").click();

    await page.locator('//*[@id="showload_hidden"]').click();
    expect(
      await page.locator('//*[@id="showload_hidden"]').isChecked()
    ).toBeTruthy();

    expect(
      await page.getByTestId("toggle-edit-load_hidden").isChecked()
    ).toBeFalsy();

    await page.locator('//*[@id="saveChangesBtn"]').click();

    await page.getByTestId("toggle-load_hidden").click();
    expect(
      await page.getByTestId("toggle-load_hidden").isChecked()
    ).toBeTruthy();

    await page.getByTestId("toggle-load_hidden").click();
    expect(
      await page.getByTestId("toggle-load_hidden").isChecked()
    ).toBeFalsy();

    await page.getByTestId("toggle-load_hidden").click();
    expect(
      await page.getByTestId("toggle-load_hidden").isChecked()
    ).toBeTruthy();

    await page.getByTestId("toggle-load_hidden").click();
    expect(
      await page.getByTestId("toggle-load_hidden").isChecked()
    ).toBeFalsy();

    await page.getByTestId("toggle-load_hidden").click();
    expect(
      await page.getByTestId("toggle-load_hidden").isChecked()
    ).toBeTruthy();
  }
});
