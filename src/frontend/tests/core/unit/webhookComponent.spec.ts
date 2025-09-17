import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to create an api key within a webhook component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const _randomApiKeyDescription =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);

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

    await page
      .getByTestId("data_webhook_draggable")
      .hover()
      .then(async () => {
        await page.waitForSelector("text=Webhook already added", {
          timeout: 30000,
        });
      });

    await page.getByTestId("btn_copy_str_endpoint").click();
    await page.waitForSelector("text=Endpoint URL copied", { timeout: 30000 });

    await page.getByTestId("title-Webhook").click();
    await page.getByTestId("edit-button-modal").click();

    await page
      .getByTestId("button_open_text_area_modal_str_edit_curl_advanced")
      .click();

    const curl = await page.getByTestId("text-area-modal").inputValue();

    const currentUrl = page.url();

    const flowId = currentUrl.split("/")[2];

    expect(curl).toContain(flowId);
  },
);

test(
  "user should be able to poll a webhook",
  { tag: ["@release", "@workspace"] },
  async ({ page, request }) => {
    await page.route("**/api/v1/config", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          webhook_polling_interval: 1000,
        }),
        headers: {
          "content-type": "application/json",
          ...route.request().headers(),
        },
      });
    });

    const _randomApiKeyDescription =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);

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

    await page
      .getByTestId("data_webhook_draggable")
      .hover()
      .then(async () => {
        await page.waitForSelector("text=Webhook already added", {
          timeout: 30000,
        });
      });

    await page.getByTestId("btn_copy_str_endpoint").click();
    await page.waitForSelector("text=Endpoint URL copied", { timeout: 30000 });

    const monitorBuildPromise = page.waitForRequest((request) =>
      request.url().includes("/monitor/build"),
    );

    const monitorBuildRequest = await monitorBuildPromise;
    expect(monitorBuildRequest).toBeTruthy();
  },
);
