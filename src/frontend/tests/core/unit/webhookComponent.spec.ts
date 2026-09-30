import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";

import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import {
  addParameterToNode,
  closeParametersPanel,
} from "../../utils/open-advanced-options";

test(
  "user should be able to create an api key within a webhook component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const _randomApiKeyDescription =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await openBlankFlow(page);
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("webhook");

    await page.waitForSelector('[data-testid="input_outputWebhook"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input_outputWebhook")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-webhook").click();
      });

    await adjustScreenView(page);

    await page
      .getByTestId("input_output_webhook_draggable")
      .hover()
      .then(async () => {
        await page.waitForSelector("text=Webhook already added", {
          timeout: 30000,
        });
      });

    await page.getByTestId("btn_copy_str_endpoint").click();
    await page.waitForSelector("text=Endpoint URL copied", { timeout: 30000 });

    await page.getByTestId("title-Webhook").click();

    // LE-1810: curl is an advanced field — surface it on the node and read
    // it there.
    await addParameterToNode(page, "curl");
    await closeParametersPanel(page);
    await adjustScreenView(page);

    await page.getByTestId("button_open_text_area_modal_str_curl").click();

    const curl = await page.getByTestId("text-area-modal").inputValue();

    const currentUrl = page.url();

    const flowId = currentUrl.split("/")[2];

    expect(curl).toContain(flowId);

    await page.getByText(TEXTS.close, { exact: true }).last().click();
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
          type: "full",
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
    await openBlankFlow(page);
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("webhook");

    await page.waitForSelector('[data-testid="input_outputWebhook"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input_outputWebhook")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-webhook").click();
      });

    await adjustScreenView(page);

    await page
      .getByTestId("input_output_webhook_draggable")
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
