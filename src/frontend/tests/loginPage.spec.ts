import { expect, test } from "@playwright/test";
import { BASE_URL_API } from "../src/constants/constants";

test.describe("Test Login Page", () => {
  const baseUrl = `http://localhost:7860${BASE_URL_API}`
  test("Test auto login GET", async ({ request }) => {
      const response = await request.get(`${baseUrl}auto_login`)
      expect(response.status()).toBe(200);
      const body = JSON.parse(await response.text())
      console.log(body)
      expect(body.access_token).toBeTruthy();
      expect(body.token_type).toBeTruthy();
  });

  test("auto_login", async ({ page }) => {
      await page.routeFromHAR("harFiles/langflow.har", {
        url: "*/api/v1/*",
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
});
