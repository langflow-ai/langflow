import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "User should be able to use components as tool",
  { tag: ["@release"] },
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
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText("toolset").count()).toBeGreaterThan(0);

    await page.keyboard.press("ControlOrMeta+Shift+m");

    await page.waitForSelector("text=toolset", {
      timeout: 3000,
      state: "hidden",
    });

    expect(await page.getByText("toolset").count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText("toolset").count()).toBeGreaterThan(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 3000,
      state: "hidden",
    });

    expect(await page.getByText("toolset").count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText("toolset").count()).toBeGreaterThan(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 3000,
      state: "hidden",
    });

    expect(await page.getByText("toolset").count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 3000,
      state: "visible",
    });

    expect(await page.getByText("toolset").count()).toBeGreaterThan(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 3000,
      state: "hidden",
    });

    expect(await page.getByText("toolset").count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector("text=toolset", {
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("disclosure-data").click();

    await page.getByTestId("disclosure-agents").click();

    await page.waitForSelector('[data-testid="agentsAgent"]', {
      timeout: 3000,
      state: "visible",
    });
    await page
      .getByTestId("agentsAgent")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-agent").click();
      });

    // Move the Agent node a bit

    await page.getByTestId("handle-url-shownode-toolset-right").first().click();

    await page.getByTestId("handle-agent-shownode-tools-left").first().click();

    expect(await page.locator(".react-flow__edge").count()).toBeGreaterThan(0);
  },
);
