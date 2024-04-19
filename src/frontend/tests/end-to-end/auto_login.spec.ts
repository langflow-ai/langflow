import { test } from "@playwright/test";

test.describe("Auto_login tests", () => {
  test("auto_login sign in", async ({ page }) => {
    await page.goto("/");
    await page.locator('//*[@id="new-project-btn"]').click();
  });

  test("auto_login block_admin", async ({ page }) => {
    await page.goto("/");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);

    await page.goto("/login");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);

    await page.goto("/admin");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);

    await page.goto("/admin/login");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);
  });
});
