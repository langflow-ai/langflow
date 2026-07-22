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
    await page.getByTestId("sidebar-search-input").fill("url");
    await page.waitForSelector('[data-testid="data_sourceURL"]', {
      timeout: 10000,
    });

    await zoomOut(page, 3);

    await page
      .getByTestId("data_sourceURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("tool calling agent");
    await page.waitForSelector(
      '[data-testid="langchain_utilitiesTool Calling Agent"]',
      {
        timeout: 10000,
      },
    );

    await page
      .getByTestId("langchain_utilitiesTool Calling Agent")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 300 },
      });

    await adjustScreenView(page);

    await page.getByTestId("title-URL").first().click();
    await page.getByTestId("tool-mode-button").click();

    //connection
    const urlOutput = await page
      .getByTestId("handle-urlcomponent-shownode-toolset-right")
      .first();

    await urlOutput.hover();
    await page.mouse.down();
    const toolCallingAgentInput = await page
      .getByTestId("handle-toolcallingagent-shownode-tools-left")
      .nth(0);
    await toolCallingAgentInput.hover();
    await page.mouse.up();

    await expect(page.locator(".react-flow__edge-interaction")).toHaveCount(2);

    // The handles resolved above by testid must also be reachable by their
    // accessible name — confirms the aria-label targets the same element.
    await expect(
      page.getByRole("button", { name: /Output handle for Toolset/ }).first(),
    ).toHaveCount(1);
    await expect(
      page.getByRole("button", { name: /Input handle for Tools/ }).first(),
    ).toHaveCount(1);

    // The newly created edge exposes an accessible name identifying the
    // connection's source and target.
    await expect(
      page.getByRole("img", { name: /^Edge from .* to .*/ }).last(),
    ).toBeVisible();
  },
);

test(
  "should delete edge on context menu delete click",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");
    await page.waitForSelector('[data-testid="data_sourceURL"]', {
      timeout: 10000,
    });

    await zoomOut(page, 3);

    await page
      .getByTestId("data_sourceURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 100 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("tool calling agent");
    await page.waitForSelector(
      '[data-testid="langchain_utilitiesTool Calling Agent"]',
      {
        timeout: 10000,
      },
    );

    await page
      .getByTestId("langchain_utilitiesTool Calling Agent")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 400, y: 300 },
      });

    await adjustScreenView(page);

    await page.getByTestId("title-URL").first().click();
    await page.getByTestId("tool-mode-button").click();

    //connection
    const urlOutput = page
      .getByTestId("handle-urlcomponent-shownode-toolset-right")
      .first();

    await urlOutput.hover();
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
    await expect(edgeContextMenu).toHaveCount(0);
  },
);
