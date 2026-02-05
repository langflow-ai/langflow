import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to edit name and description of a node",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    const randomDescription = Math.random().toString(36).substring(2, 15);

    const randomName_2 = Math.random().toString(36).substring(2, 15);
    const randomDescription_2 = Math.random().toString(36).substring(2, 15);

    const randomName_3 = Math.random().toString(36).substring(2, 15);
    const randomDescription_3 = Math.random().toString(36).substring(2, 15);

    const randomName_4 = Math.random().toString(36).substring(2, 15);
    const randomDescription_4 = Math.random().toString(36).substring(2, 15);

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await page.waitForSelector(
      '[data-testid="sidebar-custom-component-button"]',
      {
        timeout: 30000,
      },
    );

    await page.waitForTimeout(500);

    await page.getByTestId("sidebar-custom-component-button").click();

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("edit-fields-button").click();

    await page.getByTestId("showinput_value").click();

    await expect(
      page.locator(`//*[@id="popover-anchor-input-input_value"]`),
    ).not.toBeVisible();

    await page.getByTestId("showinput_value").click();

    await expect(
      page.locator(`//*[@id="popover-anchor-input-input_value"]`),
    ).toBeVisible();

    await page
      .getByTestId("popover-anchor-input-input_value")
      .fill(randomDescription);

    await page.getByTestId("publish-button").click();

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("title-Custom Component")).toBeVisible();

    await page.getByTestId("div-generic-node").click();

    // Hover over the node to reveal the edit button
    await page.getByTestId("panel-description").hover();
    await page.getByTestId("edit-name-description-button").click();

    await page.getByTestId("inspection-panel-name").fill(randomName_2);
    await page.getByTestId("edit-fields-button").click();
    await expect(page.getByTestId("node-name")).toHaveText(randomName_2);

    await page
      .getByTestId("popover-anchor-input-input_value")
      .fill(randomDescription_2);
    await page.keyboard.press("Enter");

    await expect(page.getByTestId("node-name")).toHaveText(randomName_2);

    await page.getByTestId("div-generic-node").click();

    // Hover over the node to reveal the edit button
    await page.getByTestId("panel-description").hover();
    await page.getByTestId("edit-name-description-button").click();

    await page.getByTestId(`inspection-panel-name`).fill(randomName_3);
    await page.getByTestId("edit-fields-button").click();
    await expect(page.getByTestId("node-name")).toHaveText(randomName_3);
    await page
      .getByTestId("popover-anchor-input-input_value")
      .fill(randomDescription_3);
    await page.getByTestId("div-generic-node").click();
    await expect(
      page.getByTestId("popover-anchor-input-input_value"),
    ).toHaveValue(randomDescription_3);
    await page.getByTestId("div-generic-node").click();

    await expect(page.getByTestId("node-name")).not.toHaveText(randomName_2);
    await expect(
      page.getByTestId("popover-anchor-input-input_value"),
    ).toHaveValue(randomDescription_3);

    await page.getByTestId("div-generic-node").click();

    // Hover over the node to reveal the edit button
    await page.getByTestId("panel-description").hover();
    await page.getByTestId("edit-name-description-button").click();
    await page.getByTestId(`inspection-panel-name`).fill(randomName_4);

    await page.getByTestId("edit-fields-button").click();

    await page
      .getByTestId("popover-anchor-input-input_value")
      .fill(randomDescription_4);

    await expect(page.getByTestId("node-name")).toHaveText(randomName_4);
    await expect(page.getByTestId("node-name")).not.toHaveText(randomName_3);
    await page
      .getByTestId("popover-anchor-input-input_value")
      .fill(randomDescription_4);

    await expect(
      page.getByTestId("popover-anchor-input-input_value"),
    ).toHaveValue(randomDescription_4);

    await page.getByTestId("div-generic-node").click();

    // Hover over the node to reveal the edit button
    await page.getByTestId("panel-description").hover();
    await page.getByTestId("edit-name-description-button").click();

    await page.getByTestId("inspection-panel-name").fill(randomName_3);
    await page.getByTestId("edit-fields-button").click();

    await page.keyboard.press("Escape");

    await expect(page.getByTestId("node-name")).toHaveText(randomName_3);
  },
);
