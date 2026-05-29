import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

test(
  "User should be able to use components as tool",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await openBlankFlow(page);
    await page.waitForSelector('[data-testid="disclosure-data sources"]', {
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("disclosure-data sources").click();
    await page.waitForSelector('[data-testid="data_sourceURL"]', {
      timeout: 3000,
      state: "visible",
    });
    await page
      .getByTestId("data_sourceURL")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-url").click();
      });

    await page.getByTestId("generic-node-title-arrangement").click();

    await page
      .getByTestId("generic-node-title-arrangement")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await page.keyboard.press("ControlOrMeta+Shift+m");

    await page.waitForSelector(`text=${TEXTS.labelToolset}`, {
      timeout: 5000,
      state: "visible",
    });

    expect(await page.getByText(TEXTS.labelToolset).count()).toBeGreaterThan(0);

    await page.keyboard.press("ControlOrMeta+Shift+m");

    await page.waitForSelector(`text=${TEXTS.labelToolset}`, {
      timeout: 5000,
      state: "hidden",
    });

    expect(await page.getByText(TEXTS.labelToolset).count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector(`text=${TEXTS.labelToolset}`, {
      timeout: 5000,
      state: "visible",
    });

    expect(await page.getByText(TEXTS.labelToolset).count()).toBeGreaterThan(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector(`text=${TEXTS.labelToolset}`, {
      timeout: 5000,
      state: "hidden",
    });

    expect(await page.getByText(TEXTS.labelToolset).count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector(`text=${TEXTS.labelToolset}`, {
      timeout: 5000,
      state: "visible",
    });

    expect(await page.getByText(TEXTS.labelToolset).count()).toBeGreaterThan(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector(`text=${TEXTS.labelToolset}`, {
      timeout: 5000,
      state: "hidden",
    });

    expect(await page.getByText(TEXTS.labelToolset).count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector(`text=${TEXTS.labelToolset}`, {
      timeout: 5000,
      state: "visible",
    });

    expect(await page.getByText(TEXTS.labelToolset).count()).toBeGreaterThan(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector(`text=${TEXTS.labelToolset}`, {
      timeout: 5000,
      state: "hidden",
    });

    expect(await page.getByText(TEXTS.labelToolset).count()).toBe(0);

    await page.getByTestId("tool-mode-button").click();

    await page.waitForSelector(`text=${TEXTS.labelToolset}`, {
      timeout: 5000,
      state: "visible",
    });

    await page.getByTestId("disclosure-data sources").click();

    await page.getByTestId("disclosure-models & agents").click();

    await adjustScreenView(page, { numberOfZoomOut: 4 });

    await page.waitForSelector('[data-testid="models_and_agentsAgent"]', {
      timeout: 3000,
      state: "visible",
    });
    await page
      .getByTestId("models_and_agentsAgent")
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
    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000,
    });

    await page.getByTestId("output-inspection-toolset-urlcomponent").click();

    expect(await page.getByTestId("tool_name").count()).toBeGreaterThan(0);

    expect(await page.getByTestId("tool_description").count()).toBeGreaterThan(
      0,
    );

    expect(await page.getByTestId("tool_tags").count()).toBeGreaterThan(0);
    await page.getByText(TEXTS.close).last().click();

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

    await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
      timeout: 30000,
    });

    await page
      .getByTestId("output-inspection-toolset-customcomponent")
      .last()
      .click();

    expect(await page.getByTestId("tool_name").count()).toBeGreaterThan(0);

    expect(await page.getByTestId("tool_description").count()).toBe(0);

    expect(await page.getByTestId("tool_tags").count()).toBe(0);
  },
);
