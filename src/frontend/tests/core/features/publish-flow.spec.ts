import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to publish a flow",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 5000,
    });

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 5000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");

    await page.waitForSelector('[data-testid="input_outputChat Input"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("input_outputChat Input")
      .hover({ timeout: 3000 })
      .then(async () => {
        await page
          .getByTestId("add-component-button-chat-input")
          .last()
          .click();
      });

    await page.waitForTimeout(2000);

    await adjustScreenView(page, { numberOfZoomOut: 3 });
    await page.getByTestId("publish-button").click();

    await page.waitForTimeout(3000);

    await page.waitForSelector('[data-testid="shareable-playground"]', {
      timeout: 10000,
    });

    try {
      await page.waitForTimeout(2000);

      await expect(page.getByTestId("publish-switch")).toBeVisible({
        timeout: 10000,
      });
    } catch (error) {
      console.error("Error waiting for publish operation:", error);
      throw error;
    }

    await page.waitForTimeout(2000);

    await page.getByTestId("publish-switch").click();
    const pagePromise = context.waitForEvent("page");

    await page.waitForTimeout(2000);

    await page.getByTestId("shareable-playground").click();
    const newPage = await pagePromise;
    await newPage.waitForTimeout(3000);
    const newUrl = newPage.url();
    await newPage.getByPlaceholder("Send a message...").fill("Hello");
    await newPage.getByTestId("button-send").last().click();

    const stopButton = newPage.getByRole("button", { name: "Stop" });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });

    await newPage.close();
    await page.bringToFront();
    await page.waitForTimeout(500);
    await page.getByTestId("publish-button").click();
    await page.waitForTimeout(500);
    await page.getByTestId("publish-switch").click();
    await page.waitForTimeout(500);
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();
    await expect(page.getByTestId("publish-switch")).toBeChecked({
      checked: false,
    });
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();
    await page.goto(newUrl);
    await page.waitForTimeout(2000);
    try {
      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 10000,
      });
    } catch (_error) {
      await page.reload();
      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 10000,
      });
    }
  },
);
