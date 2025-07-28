import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user should be able to use ComposIO without getting api_key error",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("composio");

    await page.waitForSelector('[data-testid="composioComposio Tools"]', {
      timeout: 3000,
    });

    const modelElement = await page.getByTestId("composioComposio Tools");
    const targetElement = await page.locator('//*[@id="react-flow-id"]');
    await modelElement.dragTo(targetElement);

    await page.mouse.up();
    await page.mouse.down();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await expect(page.getByText("api_key")).toBeVisible({
      timeout: 3000,
      visible: false,
    });
  },
);

test(
  "user should be able to use connect tools",
  { tag: ["@release", "@api", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    //first component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("search api");
    await page.waitForSelector('[data-testid="searchapiSearchApi"]', {
      timeout: 1000,
    });

    await zoomOut(page, 3);

    await page
      .getByTestId("searchapiSearchApi")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("tool calling agent");
    await page.waitForSelector(
      '[data-testid="langchain_utilitiesTool Calling Agent"]',
      {
        timeout: 1000,
      },
    );

    await page
      .getByTestId("langchain_utilitiesTool Calling Agent")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 300 },
      });

    await page.getByTestId("fit_view").click();

    await page.getByTestId("title-SearchApi").first().click();
    await page.getByTestId("tool-mode-button").click();

    //connection
    const searchApiOutput = await page
      .getByTestId("handle-searchcomponent-shownode-toolset-right")
      .first();

    await searchApiOutput.hover();
    await page.mouse.down();
    const toolCallingAgentInput = await page
      .getByTestId("handle-toolcallingagent-shownode-tools-left")
      .nth(0);
    await toolCallingAgentInput.hover();
    await page.mouse.up();

    expect(await page.locator(".react-flow__edge-interaction").count()).toBe(1);
  },
);
