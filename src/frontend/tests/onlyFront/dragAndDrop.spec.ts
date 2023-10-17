import { expect, test } from "@playwright/test";

test.describe("Auto_login tests", () => {
  test("auto_login sign in", async ({ page }) => {
    await page.routeFromHAR("harFiles/langflow.har", {
      url: "**/api/v1/**",
      update: false,
    });
    await page.goto("http:localhost:3000/");
    await page.getByRole("button", { name: "Community Examples" }).click();
    await page.waitForSelector(".community-pages-flows-panel");
    expect(
      await page
        .locator(".community-pages-flows-panel")
        .evaluate((el) => el.children)
    ).toBeTruthy();
  });
  test("auto_login block_admin", async ({ page }) => {
    await page.routeFromHAR("harFiles/langflow.har", {
      url: "**/api/v1/**",
      update: false,
    });
    await page.goto("http:localhost:3000/");
    await page.getByRole("button", { name: "Community Examples" }).click();
    await page.goto("http:localhost:3000/login");
    await page.getByRole("button", { name: "Community Examples" }).click();
    await page.goto("http:localhost:3000/admin");
    await page.getByRole("button", { name: "Community Examples" }).click();
    await page.goto("http:localhost:3000/admin/login");
    await page.getByRole("button", { name: "Community Examples" }).click();
  });
});
