import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test(
  "should create edge between components",
  { tag: ["@release", "@workspace"] },
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

    await adjustScreenView(page);

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

    expect(await page.locator(".react-flow__edge-interaction").count()).toBe(2);
  },
);

test(
  "should delete edge on context menu delete click",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

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
        targetPosition: { x: 400, y: 300 },
      });

    await adjustScreenView(page);

    await page.getByTestId("title-SearchApi").first().click();
    await page.getByTestId("tool-mode-button").click();

    //connection
    const searchApiOutput = page
      .getByTestId("handle-searchcomponent-shownode-toolset-right")
      .first();

    await searchApiOutput.hover();
    await page.mouse.down();
    const toolCallingAgentInput = page
      .getByTestId("handle-toolcallingagent-shownode-tools-left")
      .nth(0);
    await toolCallingAgentInput.hover();
    await page.mouse.up();

    await page
      .getByTestId("edge-context-menu-trigger")
      .click({ button: "right" });
    await page.getByTestId("context-menu-item-destructive").click();

    const edgeContextMenu = page.getByTestId("edge-context-menu-trigger");
    expect(edgeContextMenu).toHaveCount(0);
  },
);
