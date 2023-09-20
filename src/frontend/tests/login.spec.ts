import { test } from "@playwright/test";

test.describe("Login", () => {
  test("har_file", async ({ page }) => {
    await page.routeFromHAR("harFiles/login.har", {
      url: "**/api/v1/**",
      update: true,
      updateMode: "minimal",
      updateContent: "embed",
    });

    await page.goto("http://localhost:3000/");
    await page.waitForURL("http://localhost:3000/login");
    await page.waitForURL("http://localhost:3000/login", { timeout: 100 });
    await page.getByPlaceholder("Username").click();
    await page.close();
  });
});
