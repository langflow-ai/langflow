import { test } from "@playwright/test";

test.describe("Auto_login tests", () => {
  test("auto_login sign in", async ({ page }) => {
    await page.routeFromHAR("harFiles/langflow.har", {
      url: "**/api/v1/**",
      update: false,
    });
    await page.goto("http:localhost:3000/");
    await page.locator('//*[@id="new-project-btn"]').click();
  });

  test("auto_login block_admin", async ({ page }) => {
    await page.routeFromHAR("harFiles/langflow.har", {
      url: "**/api/v1/**",
      update: false,
    });
    await page.goto("http:localhost:3000/");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.goto("http:localhost:3000/login");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.goto("http:localhost:3000/admin");
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.goto("http:localhost:3000/admin/login");
    await page.locator('//*[@id="new-project-btn"]').click();
  });
});
