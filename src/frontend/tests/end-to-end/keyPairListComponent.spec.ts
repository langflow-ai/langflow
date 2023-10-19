import { expect, test } from "@playwright/test";

test("KeypairListComponent", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("csv");

  await page.waitForTimeout(2000);

  await page
    .locator('//*[@id="sideCSVLoader"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.locator('//*[@id="keypair0"]').click();
  await page.locator('//*[@id="keypair0"]').fill("testtesttesttest");
  await page.locator('//*[@id="keypair100"]').click();
  await page
    .locator('//*[@id="keypair100"]')
    .fill("test test test test test test");

  const valueWithSpace = await page
    .locator('//*[@id="keypair100"]')
    .inputValue();

  if (valueWithSpace !== "test test test test test test") {
    expect(false).toBeTruthy();
  }

  const plusButtonLocatorNode = page.locator('//*[@id="plusbtn0"]');
  const elementCountNode = await plusButtonLocatorNode.count();
  if (elementCountNode > 0) {
    await plusButtonLocatorNode.click();
  }

  await page.locator('//*[@id="keypair1"]').click();
  await page.locator('//*[@id="keypair1"]').fill("testtesttesttest1");
  await page.locator('//*[@id="keypair101"]').click();
  await page.locator('//*[@id="keypair101"]').fill("testtesttesttesttesttest1");
  await page.locator('//*[@id="plusbtn1"]').click();

  await page.locator('//*[@id="keypair2"]').click();
  await page.locator('//*[@id="keypair2"]').fill("testtesttesttest2");
  await page.locator('//*[@id="keypair102"]').click();
  await page.locator('//*[@id="keypair102"]').fill("testtesttesttesttesttest2");

  await page.locator('//*[@id="minusbtn1"]').click();

  const keyPairVerification = page.locator('//*[@id="keypair102"]');
  const elementKeyCount = await keyPairVerification.count();

  if (elementKeyCount === 0) {
    expect(true).toBeTruthy();
  } else {
    expect(false).toBeTruthy();
  }

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div[1]/div/div[2]/div/div/div[1]/div/div[1]/div'
    )
    .click();
  await page.locator('//*[@id="advancedIcon"]').click();
  await page.locator('//*[@id="editAdvancedBtn"]').click();

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

    await page
      .locator(
        '//*[@id="react-flow-id"]/div[1]/div[1]/div[1]/div/div[2]/div/div/div[1]/div/div[1]/div'
      )
      .click();
    await page.locator('//*[@id="advancedIcon"]').click();
    await page.locator('//*[@id="editAdvancedBtn"]').click();

    await page.locator('//*[@id="showfile_path"]').click();
    expect(
      await page.locator('//*[@id="showfile_path"]').isChecked()
    ).toBeTruthy();
    await page.locator('//*[@id="showmetadata"]').click();
    expect(
      await page.locator('//*[@id="showmetadata"]').isChecked()
    ).toBeTruthy();

    await page.locator('//*[@id="keypair0"]').click();
    await page.locator('//*[@id="keypair0"]').fill("testtesttesttest");
    await page.locator('//*[@id="keypair100"]').click();
    await page
      .locator('//*[@id="keypair100"]')
      .fill("test test test test test test");

    const plusButtonLocator = page.locator('//*[@id="plusbtn0"]');
    const elementCount = await plusButtonLocator.count();
    if (elementCount > 0) {
      await plusButtonLocator.click();
    }

    await page.locator('//*[@id="keypair1"]').click();
    await page.locator('//*[@id="keypair1"]').fill("testtesttesttest1");
    await page.locator('//*[@id="keypair101"]').click();
    await page
      .locator('//*[@id="keypair101"]')
      .fill("testtesttesttesttesttest1");
    await page.locator('//*[@id="plusbtn1"]').click();

    await page.locator('//*[@id="keypair2"]').click();
    await page.locator('//*[@id="keypair2"]').fill("testtesttesttest2");
    await page.locator('//*[@id="keypair102"]').click();
    await page
      .locator('//*[@id="keypair102"]')
      .fill("testtesttesttesttesttest2");

    await page.locator('//*[@id="minusbtn1"]').click();

    const keyPairVerification = page.locator('//*[@id="keypair102"]');
    const elementKeyCount = await keyPairVerification.count();

    if (elementKeyCount === 0) {
      await page.locator('//*[@id="saveChangesBtn"]').click();

      const key1 = await page.locator('//*[@id="keypair0"]').inputValue();
      const value1 = await page.locator('//*[@id="keypair100"]').inputValue();
      const key2 = await page.locator('//*[@id="keypair1"]').inputValue();
      const value2 = await page.locator('//*[@id="keypair101"]').inputValue();

      if (
        key1 === "testtesttesttest" &&
        value1 === "test test test test test test" &&
        key2 === "testtesttesttest2" &&
        value2 === "testtesttesttesttesttest2"
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
