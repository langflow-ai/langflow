import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import {
  closeParametersPanel,
  openParametersPanel,
  toggleParameterOnNode,
} from "../../utils/open-advanced-options";

test(
  "KeypairListComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);

    // Allow for legacy components
    await page.getByTestId("sidebar-options-trigger").click();
    await page.getByTestId("sidebar-legacy-switch").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("amazon bedrock");

    await page.waitForSelector('[data-testid="amazonAmazon Bedrock"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("amazonAmazon Bedrock")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await page.getByTestId("div-generic-node").click();

    // LE-1810: the parameters panel adds the hidden field to the node; the
    // values are edited on the node itself.
    await openParametersPanel(page);

    await toggleParameterOnNode(page, "model_kwargs");
    await expect(
      page.getByTestId("inspector-remove-model_kwargs"),
    ).toBeVisible();
    await closeParametersPanel(page);

    await adjustScreenView(page, {
      numberOfZoomOut: 2,
    });

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

    await expect(page.locator('//*[@id="keypair100"]')).toHaveCount(1);

    await openParametersPanel(page);

    await closeParametersPanel(page);

    await expect(page.locator('//*[@id="plusbtn0"]')).toHaveCount(1);
    await page.getByTestId("div-generic-node").click();

    // LE-1810: values are edited on the node, not in the panel
    await page.locator('//*[@id="keypair0"]').click();
    await page.locator('//*[@id="keypair0"]').fill("testtesttesttest");

    await expect(page.locator('//*[@id="keypair0"]')).toHaveCount(1);
    await page.getByTestId("div-generic-node").click();

    await expect(page.locator('//*[@id="keypair0"]')).toHaveValue(
      "testtesttesttest",
    );
    await expect(page.locator('//*[@id="keypair100"]')).toHaveValue(
      "test test test test test test",
    );
    await page.getByTestId("div-generic-node").click();
  },
);
