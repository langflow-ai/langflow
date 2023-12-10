import { Page, test } from "@playwright/test";

test.describe("Flow Page tests", () => {
  async function goToFlowPage(page: Page) {
    await page.goto("http://localhost:3000/");
    await page.getByRole("button", { name: "New Project" }).click();
  }

  test("save", async ({ page }) => {
    await goToFlowPage(page);
    await page.getByRole("button", { name: "Custom" }).click();
    await page
      .locator("div")
      .filter({ hasText: /^Custom Component$/ })
      .nth(4)
      .dragTo(page.locator(".react-flow__pane"));

    // await page.getByTestId("icon-ExternalLink").click();
    // await page.locator('//*[@id="checkAndSaveBtn"]').click();
  });
});
