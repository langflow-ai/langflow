import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "User should be able to use components as tool",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="disclosure-vector stores"]', {
      timeout: 3000,
      state: "visible",
    });

    await page.getByTestId("disclosure-vector stores").click();
    await page.waitForSelector('[data-testid="vectorstoresAstra DB"]', {
      timeout: 3000,
      state: "visible",
    });
    await page
      .getByTestId("vectorstoresAstra DB")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-astra-db").click();
      });

    await page.getByTestId("generic-node-title-arrangement").click();

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

    await page.getByTestId("disclosure-vector stores").click();

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

    await page
      .getByTestId("handle-astradb-shownode-toolset-right")
      .first()
      .click();

    await page.getByTestId("handle-agent-shownode-tools-left").first().click();

    expect(await page.locator(".react-flow__edge").count()).toBeGreaterThan(0);
  },
);
