import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { zoomOut } from "../../utils/zoom-out";

test(
  "User should be able to use components as tool",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="disclosure-data"]', {
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("disclosure-data").click();
    await page.waitForSelector('[data-testid="dataURL"]', {
      timeout: 3000,
      state: "visible",
    });
    await page
      .getByTestId("dataURL")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-url").click();
      });

    await page.getByTestId("generic-node-title-arrangement").click();

    await page
      .getByTestId("generic-node-title-arrangement")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await page.keyboard.press("ControlOrMeta+Shift+m");

    await page.waitForSelector("text=toolset", {
      timeout: 5000,
      state: "visible",
    });

    expect(await page.getByText("toolset").count()).toBeGreaterThan(0);

    await page.keyboard.press("ControlOrMeta+Shift+m");

    await page.waitForSelector("text=toolset", {
      timeout: 5000,
      state: "hidden",
    });

    expect(await page.getByText("toolset").count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 5000,
      state: "visible",
    });

    expect(await page.getByText("toolset").count()).toBeGreaterThan(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 5000,
      state: "hidden",
    });

    expect(await page.getByText("toolset").count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 5000,
      state: "visible",
    });

    expect(await page.getByText("toolset").count()).toBeGreaterThan(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 5000,
      state: "hidden",
    });

    expect(await page.getByText("toolset").count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 5000,
      state: "visible",
    });

    expect(await page.getByText("toolset").count()).toBeGreaterThan(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 5000,
      state: "hidden",
    });

    expect(await page.getByText("toolset").count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 5000,
      state: "visible",
    });

    await page.getByTestId("disclosure-data").click();

    await page.getByTestId("disclosure-agents").click();

    await adjustScreenView(page, { numberOfZoomOut: 4 });

    await page.waitForSelector('[data-testid="agentsAgent"]', {
      timeout: 3000,
      state: "visible",
    });
    await page
      .getByTestId("agentsAgent")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 500 },
      });
    await adjustScreenView(page);

    // Move the Agent node a bit

    await page
      .getByTestId("handle-urlcomponent-shownode-toolset-right")
      .first()
      .click();

    await page.getByTestId("handle-agent-shownode-tools-left").first().click();

    expect(await page.locator(".react-flow__edge").count()).toBeGreaterThan(0);

    await page.getByTestId("button_run_url").click();
    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page.getByTestId("output-inspection-toolset-urlcomponent").click();

    expect(await page.getByTestId("tool_name").count()).toBeGreaterThan(0);

    expect(await page.getByTestId("tool_description").count()).toBeGreaterThan(
      0,
    );

    expect(await page.getByTestId("tool_tags").count()).toBeGreaterThan(0);
    await page.getByText("Close").last().click();

    await page.getByTestId("sidebar-custom-component-button").click();

    await page.getByTestId("title-Custom Component").click();

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector(
      '[data-testid="output-inspection-toolset-customcomponent"]',
      {
        timeout: 100000,
      },
    );

    await page.waitForTimeout(1000);

    await page.getByTestId("button_run_custom component").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page
      .getByTestId("output-inspection-toolset-customcomponent")
      .last()
      .click();

    expect(await page.getByTestId("tool_name").count()).toBeGreaterThan(0);

    expect(await page.getByTestId("tool_description").count()).toBe(0);

    expect(await page.getByTestId("tool_tags").count()).toBe(0);
  },
);
