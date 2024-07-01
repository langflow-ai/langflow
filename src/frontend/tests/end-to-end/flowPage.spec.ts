import { test } from "@playwright/test";

test.describe("Flow Page tests", () => {
  test("save", async ({ page }) => {
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

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="extended-disclosure"]', {
      timeout: 30000,
    });
    await page.getByTestId("extended-disclosure").click();
    await page.getByPlaceholder("Search").click();
    await page.getByPlaceholder("Search").fill("custom");

    await page.waitForTimeout(1000);

    await page
      .locator('//*[@id="helpersCustom Component"]')
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.getByTitle("fit view").click();
    await page.getByTitle("zoom out").click();
    await page.getByTitle("zoom out").click();
    await page.getByTitle("zoom out").click();
  });
});
