import { test,expect } from "@playwright/test";

test.describe("test_examples", () => {
  test("", async ({ page }) => {
    await page.routeFromHAR("harFiles/langflow.har", {
      url: "**/api/v1/**",
      update: false,
    });
    const id = process.env.FLOWID??"123";
    const apiKey = process.env.APIKEY_OPEN_AI??"openAIkey";
    await page.route("**/api/v1/flows/", async (route) => {
      if (route.request().method() === "POST") {
        route.fulfill({
          status: 201,
          body: JSON.stringify({  id }),
        });
      }
    });
    await page.goto("http://localhost:3000/");
    await page.getByRole("button", { name: "Community Examples" }).click();
    await page.waitForSelector(".community-pages-flows-panel");
    await page
      .locator(".card-component-footer-arrangement > .inline-flex")
      .first()
      .click();
      await page.waitForURL("http://localhost:3000/flow/123",{timeout:1000})
      await page.getByPlaceholder('Type something...').nth(1).click();
      await page.getByPlaceholder('Type something...').nth(1).fill(apiKey);
      await page.locator('.round-button-form').click();

  });
});
