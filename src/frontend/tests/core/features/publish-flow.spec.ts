import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "Publish feature test",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page, context }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 3000,
    });
    // retrieve the flow id from the url
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
    await page.getByTestId("inputsChat Input").hover({ timeout: 3000 });
    await page.getByTestId("add-component-button-chat-input").click();

    await adjustScreenView(page);
    // check if clicking the publish without active it before will do nothing
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

    await page.getByTestId("shareable-playground").click();
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();
    await page.getByTestId("publish-button").click();
    await page.getByTestId("publish-switch").click();
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();
    await expect(page.getByTestId("publish-switch")).toBeChecked();
    const pagePromise = context.waitForEvent("page");
    await page.getByTestId("shareable-playground").click();
    const newPage = await pagePromise;
    await newPage.waitForTimeout(3000);
    const newUrl = newPage.url();
    await newPage.getByPlaceholder("Send a message...").fill("Hello");
    await newPage.getByTestId("button-send").click();
    await expect(newPage.getByText("Hello")).toBeVisible();
    await newPage.close();
    await page.bringToFront();
    // check if deactivate the publishworks
    await page.getByTestId("publish-button").click();
    await page.getByTestId("publish-switch").click();
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();
    await expect(page.getByTestId("publish-switch")).toBeChecked({
      checked: false,
    });
    await page.getByTestId("shareable-playground").click();
    await expect(page.getByTestId("rf__wrapper")).toBeVisible();
    // navigate to the new page
    await page.goto(newUrl);
    await expect(page.getByTestId("mainpage_title")).toBeVisible();
  },
);
