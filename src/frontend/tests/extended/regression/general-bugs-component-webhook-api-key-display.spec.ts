import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { extractAndCleanCode } from "../../utils/extract-and-clean-code";
import { loginLangflow } from "../../utils/login-langflow";

test(
  "user must be able to see api key in webhook component when auto login is disabled",
  { tag: ["@release"] },
  async ({ page }) => {
    await page.route("**/api/v1/auto_login", (route) => {
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          detail: { auto_login: false },
        }),
      });
    });

    await page.route("**/api/v1/config", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          webhook_auth_enable: true,
        }),
        headers: {
          "content-type": "application/json",
          ...route.request().headers(),
        },
      });
    });

    await loginLangflow(page);

    await awaitBootstrapTest(page, { skipGoto: true });

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();

    await page.getByTestId("sidebar-search-input").fill("webhook");

    await page.waitForSelector('[data-testid="dataWebhook"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("dataWebhook")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-webhook").click();
      });

    await adjustScreenView(page);

    await page.getByTestId("title-Webhook").click();

    await page.getByTestId("edit-button-modal").click();

    await page
      .getByTestId("button_open_text_area_modal_str_edit_curl_advanced")
      .click();

    const curl = await page.getByTestId("text-area-modal").inputValue();

    expect(curl).toContain("x-api-key");
  },
);

test(
  "user must be able to not see api key in webhook component when auto login is enabled",
  { tag: ["@release"] },
  async ({ page }) => {
    await page.route("**/api/v1/config", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          webhook_auth_enable: false,
        }),
        headers: {
          "content-type": "application/json",
          ...route.request().headers(),
        },
      });
    });

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();

    await page.getByTestId("sidebar-search-input").fill("webhook");

    await page.waitForSelector('[data-testid="dataWebhook"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("dataWebhook")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-webhook").click();
      });

    await adjustScreenView(page);

    await page.getByTestId("title-Webhook").click();

    await page.getByTestId("edit-button-modal").click();

    await page
      .getByTestId("button_open_text_area_modal_str_edit_curl_advanced")
      .click();

    const curl = await page.getByTestId("text-area-modal").inputValue();

    expect(curl).not.toContain("x-api-key");
  },
);
