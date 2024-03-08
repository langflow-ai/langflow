import { expect, test } from "@playwright/test";

test("KeypairListComponent", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("csv");

  await page.waitForTimeout(2000);

  await page
    .getByTestId("documentloadersCSVLoader")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.locator('//*[@id="keypair0"]').click();
  await page.locator('//*[@id="keypair0"]').fill("testtesttesttest");
  await page.locator('//*[@id="keypair100"]').click();
  await page
    .locator('//*[@id="keypair100"]')
    .fill("test test test test test test");

  await page.getByTestId("div-generic-node").click();

  const valueWithSpace = await page.getByTestId("keypair100").inputValue();
  await page.getByTestId("div-generic-node").click();

  if (valueWithSpace !== "test test test test test test") {
    expect(false).toBeTruthy();
  }

  const plusButtonLocatorNode = page.locator('//*[@id="plusbtn0"]');
  const elementCountNode = await plusButtonLocatorNode.count();
  if (elementCountNode > 0) {
    await plusButtonLocatorNode.click();
  }
  await page.getByTestId("div-generic-node").click();

  await page.locator('//*[@id="keypair0"]').click();
  await page.locator('//*[@id="keypair0"]').fill("testtesttesttest1");
  await page.getByTestId("div-generic-node").click();

  const keyPairVerification = page.locator('//*[@id="keypair100"]');
  const elementKeyCount = await keyPairVerification.count();

  if (elementKeyCount === 1) {
    expect(true).toBeTruthy();
  } else {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  await page.locator('//*[@id="showfile_path"]').click();
  expect(
    await page.locator('//*[@id="showfile_path"]').isChecked()
  ).toBeFalsy();
  await page.locator('//*[@id="showmetadata"]').click();
  expect(await page.locator('//*[@id="showmetadata"]').isChecked()).toBeFalsy();
  await page.locator('//*[@id="saveChangesBtn"]').click();

  const plusButtonLocator = page.locator('//*[@id="plusbtn0"]');
  const elementCount = await plusButtonLocator.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();
    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("edit-button-modal").click();

    await page.locator('//*[@id="showfile_path"]').click();
    expect(
      await page.locator('//*[@id="showfile_path"]').isChecked()
    ).toBeTruthy();
    await page.locator('//*[@id="showmetadata"]').click();
    expect(
      await page.locator('//*[@id="showmetadata"]').isChecked()
    ).toBeTruthy();

    await page.locator('//*[@id="editNodekeypair0"]').click();
    await page.locator('//*[@id="editNodekeypair0"]').fill("testtesttesttest");

    const keyPairVerification = page.locator('//*[@id="editNodekeypair0"]');
    const elementKeyCount = await keyPairVerification.count();

    if (elementKeyCount === 1) {
      await page.locator('//*[@id="saveChangesBtn"]').click();

      await page.getByTestId("div-generic-node").click();

      const key1 = await page.locator('//*[@id="keypair0"]').inputValue();
      const value1 = await page.locator('//*[@id="keypair100"]').inputValue();
      await page.getByTestId("div-generic-node").click();

      if (
        key1 === "testtesttesttest" &&
        value1 === "test test test test test test"
      ) {
        expect(true).toBeTruthy();
      } else {
        expect(false).toBeTruthy();
      }
    } else {
      expect(false).toBeTruthy();
    }
  } else {
    expect(false).toBeTruthy();
  }
});
