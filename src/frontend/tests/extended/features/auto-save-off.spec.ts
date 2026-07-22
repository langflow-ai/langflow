import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { openFlowCard } from "../../utils/flow/open-flow-card";

test(
  "user should be able to manually save a flow when the auto_save is off",
  { tag: ["@release", "@api", "@database", "@components"] },
  async ({ page }) => {
    await page.route("**/api/v1/config", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "full",
          auto_saving: false,
          frontend_timeout: 0,
        }),
        headers: {
          "content-type": "application/json",
          ...route.request().headers(),
        },
      });
    });
    await openBlankFlow(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");

    await page.waitForSelector('[data-testid="data_sourceURL"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("data_sourceURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 5000,
    });

    await adjustScreenView(page);

    expect(await page.getByTestId("save-flow-button").isEnabled()).toBeTruthy();

    await page.waitForSelector("text=loading", {
      state: "hidden",
      timeout: 5000,
    });

    await page.getByTestId("icon-ChevronLeft").last().click();

    try {
      await page.waitForSelector(
        'text="Unsaved changes will be permanently lost."',
        {
          state: "visible",
          timeout: 2000,
        },
      );

      await page.getByText("Exit Anyway", { exact: true }).click();
    } catch (_error) {
      console.error("Warning text not visible, skipping dialog confirmation");
    }

    await openFlowCard(page, "New Flow");

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 5000,
    });

    const nvidiaNode = await page.getByTestId("div-generic-node").count();
    expect(nvidiaNode).toBe(0);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");

    await page.keyboard.press("Escape");
    await page.locator('//*[@id="react-flow-id"]').click();

    const lastUrlComponent = page.getByTestId("data_sourceURL").last();
    await lastUrlComponent.scrollIntoViewIfNeeded();

    try {
      await lastUrlComponent.hover({ timeout: 5000 });

      // Wait for the add component button to appear
      await page.getByTestId("add-component-button-url").waitFor({
        state: "visible",
        timeout: 5000,
      });

      await page.getByTestId("add-component-button-url").click();
    } catch (error) {
      console.error("Failed to hover or find add component button:", error);
      throw error;
    }

    // Wait for fit view button
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 5000,
    });

    await adjustScreenView(page);

    await page.getByTestId("icon-ChevronLeft").last().click();

    await page.getByText("Save And Exit", { exact: true }).click();

    await openFlowCard(page, "New Flow");

    await page.waitForSelector("text=loading", {
      state: "hidden",
      timeout: 5000,
    });

    await expect(page.getByTestId("title-URL").first()).toBeVisible({
      timeout: 5000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("url");

    await page.waitForSelector('[data-testid="data_sourceURL"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("data_sourceURL")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 5000,
    });

    await adjustScreenView(page);

    await page.getByTestId("save-flow-button").click();
    await page.getByTestId("icon-ChevronLeft").last().click();

    const replaceButton = await page.getByTestId("replace-button").isVisible();

    if (replaceButton) {
      await page.getByTestId("replace-button").click();
    }

    const saveExitButton = await page
      .getByText("Save And Exit", { exact: true })
      .last()
      .isVisible();

    if (saveExitButton) {
      await page.getByText("Save And Exit", { exact: true }).last().click();
    }

    await openFlowCard(page, "New Flow");

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 5000,
    });

    await expect(page.getByTestId("title-URL").first()).toBeVisible({
      timeout: 5000,
    });

    const urlNumber = await page.getByTestId("title-URL").count();
    expect(urlNumber).toBe(2);
  },
);
