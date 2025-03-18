import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to publish a flow",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 3000,
    });
    const flowId = page.url().split("/").pop();
    expect(flowId).toBeDefined();
    expect(flowId).not.toBeNull();
    expect(flowId!.length).toBeGreaterThan(0);
    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 3000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");

    await page.waitForSelector('[data-testid="inputsChat Input"]', {
      timeout: 3000,
    });
    await page
      .getByTestId("inputsChat Input")
      .hover({ timeout: 3000 })
      .then(async () => {
        await page.getByTestId("add-component-button-chat-input").click();
      });

    await adjustScreenView(page);
    await page.getByTestId("publish-button").click();
    await page.waitForSelector('[data-testid="shareable-playground"]', {
      timeout: 3000,
    });
    await expect(
      page.waitForResponse(
        (response) =>
          response.url().includes(flowId!) && response.status() === 200,
      ),
    ).resolves.toBeTruthy();

    await page.getByTestId("publish-switch").click();
    const pagePromise = context.waitForEvent("page");
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
    // check if deactivate the publishworks
    await page.getByTestId("publish-button").click();
    await page.getByTestId("publish-switch").click();
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();
    await expect(page.getByTestId("publish-switch")).toBeChecked({
      checked: false,
    });
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();
    await page.goto(newUrl);
    try {
      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 10000,
      });
    } catch (error) {
      await page.reload();
      await expect(page.getByTestId("mainpage_title")).toBeVisible({
        timeout: 10000,
      });
    }
  },
);
