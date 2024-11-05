import { test } from "@playwright/test";

test.describe("Flow Page tests", () => {
  test("save", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

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
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForTimeout(3000);
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    await page.getByTestId("blank-flow").click();

    await page.waitForTimeout(1000);

    await page.getByTestId("sidebar-custom-component-button").click();

    await page.getByTitle("fit view").click();
    await page.getByTitle("zoom out").click();
    await page.getByTitle("zoom out").click();
    await page.getByTitle("zoom out").click();
  });
});
