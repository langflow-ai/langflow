import { test } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  await page.waitForTimeout(1000);
  test.setTimeout(120000);
});
test.describe("Auto_login tests", () => {
  test("auto_login sign in", async ({ page }) => {
    await page.goto("http:localhost:3000/");
    await page.locator('//*[@id="new-project-btn"]').click();
  });

  test("auto_login block_admin", async ({ page }) => {
    await page.goto("http:localhost:3000/");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);

    await page.goto("http:localhost:3000/login");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);

    await page.goto("http:localhost:3000/admin");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);

    await page.goto("http:localhost:3000/admin/login");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);
  });
});
