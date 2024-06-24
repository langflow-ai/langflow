import { test } from "@playwright/test";

test.describe("Auto_login tests", () => {
  test("auto_login sign in", async ({ page }) => {
    await page.goto("/");
    await page.getByText("New Project", { exact: true }).click();
  });

  test("auto_login block_admin", async ({ page }) => {
    await page.goto("/");
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);

    await page.goto("/login");
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);

    await page.goto("/admin");
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);

    await page.goto("/admin/login");
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
  });
});
