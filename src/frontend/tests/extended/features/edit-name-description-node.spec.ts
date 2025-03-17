import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to edit name and description of a node",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    const randomName = Math.random().toString(36).substring(2, 15);
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

    await page.getByTestId("edit-name-description-button").click();

    await page.getByTestId("input-title-Custom Component").fill(randomName);

    await page.getByTestId("textarea").fill(randomDescription);

    await page.getByTestId("publish-button").click();

    await page.keyboard.press("Escape");

    expect(await page.getByText(randomName).count()).toBe(1);
    expect(await page.getByText(randomDescription).count()).toBe(1);

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("edit-name-description-button").click();

    await page.getByTestId(`input-title-${randomName}`).fill(randomName_2);

    await page.getByTestId("textarea").fill(randomDescription_2);

    await page.getByTestId("save-name-description-button").click();

    expect(await page.getByText(randomName_2).count()).toBe(1);
    expect(await page.getByText(randomDescription_2).count()).toBe(1);

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("edit-name-description-button").click();

    await page.getByTestId(`input-title-${randomName_2}`).fill(randomName_3);

    await page.keyboard.press("Enter");

    expect(await page.getByText(randomName_3).count()).toBe(1);

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("edit-name-description-button").click();

    await page.getByTestId(`input-title-${randomName_3}`).fill(randomName_4);

    await page.getByTestId("textarea").fill(randomDescription_4);

    await page.keyboard.press("Escape");

    expect(await page.getByText(randomName_4).count()).toBe(1);

    expect(await page.getByText(randomDescription_2).count()).toBe(1);

    expect(await page.getByText(randomDescription_4).count()).toBe(0);

    expect(await page.getByText(randomName_3).count()).toBe(0);

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("edit-name-description-button").click();

    await page.getByTestId("textarea").fill(randomDescription_3);

    await page.getByTestId(`input-title-${randomName_4}`).fill(randomName_3);

    await page.keyboard.press("Escape");

    expect(await page.getByText(randomDescription_3).count()).toBe(1);

    expect(await page.getByText(randomName_4).count()).toBe(1);

    expect(await page.getByText(randomName_3).count()).toBe(0);

    expect(await page.getByText(randomDescription_4).count()).toBe(0);
  },
);
