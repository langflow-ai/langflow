import { expect, test } from "@playwright/test";

test("auto_login", async ({ page }) => {
  await page.routeFromHAR("harFiles/langflow.har", {
    url: "**/api/v1/**",
    update: false,
  });
  await page.goto("http://localhost:3000/");
  await page.getByRole("button", { name: "Community Examples" }).click();
  await page.waitForSelector(".community-pages-flows-panel");
  expect(
    await page
      .locator(".community-pages-flows-panel")
      .evaluate((el) => el.children)
  ).toBeTruthy();
});
