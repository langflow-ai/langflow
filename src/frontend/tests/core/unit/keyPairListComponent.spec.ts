import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "KeypairListComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("amazon bedrock");

    await page.waitForSelector('[data-testid="modelsAmazon Bedrock"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("modelsAmazon Bedrock")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await adjustScreenView(page);

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();

    await page.getByTestId("showmodel_kwargs").click();
    expect(await page.getByTestId("showmodel_kwargs").isChecked()).toBeTruthy();
    await page.getByText("Close").last().click();

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
    const elementCountNode = await plusButtonLocatorNode?.count();
    if (elementCountNode > 0) {
      await plusButtonLocatorNode.click();
    }
    await page.getByTestId("div-generic-node").click();

    await page.locator('//*[@id="keypair0"]').click();
    await page.locator('//*[@id="keypair0"]').fill("testtesttesttest1");
    await page.getByTestId("div-generic-node").click();

    const keyPairVerification = page.locator('//*[@id="keypair100"]');
    const elementKeyCount = await keyPairVerification?.count();

    if (elementKeyCount === 1) {
      expect(true).toBeTruthy();
    } else {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();

    await page.getByText("Close").last().click();

    const plusButtonLocator = page.locator('//*[@id="plusbtn0"]');
    const elementCount = await plusButtonLocator?.count();
    if (elementCount === 1) {
      expect(true).toBeTruthy();
      await page.getByTestId("div-generic-node").click();

      await page.getByTestId("more-options-modal").click();
      await page.getByTestId("advanced-button-modal").click();

      await page.locator('//*[@id="editNodekeypair0"]').click();
      await page
        .locator('//*[@id="editNodekeypair0"]')
        .fill("testtesttesttest");

      const keyPairVerification = page.locator('//*[@id="editNodekeypair0"]');
      const elementKeyCount = await keyPairVerification?.count();

      if (elementKeyCount === 1) {
        await page.getByText("Close").last().click();

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
  },
);
