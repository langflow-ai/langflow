import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to manually save a flow when the auto_save is off",
  { tag: ["@release", "@api", "@database", "@components"] },
  async ({ page }) => {
    await page.route("**/api/v1/config", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          auto_saving: false,
          frontend_timeout: 0,
        }),
        headers: {
          "content-type": "application/json",
          ...route.request().headers(),
        },
      });
    });

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 5000,
    });

    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("NVIDIA");

    await page.waitForSelector('[data-testid="languagemodelsNVIDIA"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("languagemodelsNVIDIA")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 5000,
    });

    await page.getByTestId("fit_view").click();

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
    } catch (error) {
      console.log("Warning text not visible, skipping dialog confirmation");
    }

    await page.getByText("Untitled document").first().click();

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 5000,
    });

    const nvidiaNode = await page.getByTestId("div-generic-node").count();
    expect(nvidiaNode).toBe(0);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("NVIDIA");

    await page.keyboard.press("Escape");
    await page.locator('//*[@id="react-flow-id"]').click();

    const lastNvidiaModel = page.getByTestId("languagemodelsNVIDIA").last();
    await lastNvidiaModel.scrollIntoViewIfNeeded();

    try {
      await lastNvidiaModel.hover({ timeout: 5000 });

      // Wait for the add component button to appear
      await page.getByTestId("add-component-button-nvidia").waitFor({
        state: "visible",
        timeout: 5000,
      });

      await page.getByTestId("add-component-button-nvidia").click();
    } catch (error) {
      console.error("Failed to hover or find add component button:", error);
      throw error;
    }

    // Wait for fit view button
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 5000,
    });

    await page.getByTestId("fit_view").click();

    await page.getByTestId("icon-ChevronLeft").last().click();

    await page.getByText("Save And Exit", { exact: true }).click();

    await page.getByText("Untitled document").first().click();

    await page.waitForSelector("text=loading", {
      state: "hidden",
      timeout: 5000,
    });

    await expect(page.getByTestId("title-NVIDIA").first()).toBeVisible({
      timeout: 5000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("NVIDIA");

    await page.waitForSelector('[data-testid="languagemodelsNVIDIA"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("languagemodelsNVIDIA")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 5000,
    });

    await page.getByTestId("fit_view").click();

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

    await page.getByText("Untitled document").first().click();

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 5000,
    });

    await expect(page.getByTestId("title-NVIDIA").first()).toBeVisible({
      timeout: 5000,
    });

    const nvidiaNumber = await page.getByTestId("title-NVIDIA").count();
    expect(nvidiaNumber).toBe(2);
  },
);
