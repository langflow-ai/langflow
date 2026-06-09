import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user must be able to minimize and expand a component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);

    await addLegacyComponents(page);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill(TEXTS.searchTextInput);
    await page.waitForSelector('[data-testid="input_outputText Input"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("input_outputText Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));

    await page
      .locator('//*[@id="react-flow-id"]')
      .hover()
      .then(async () => {
        await page.mouse.down();
        await page.mouse.move(-800, 300);
      });

    await page.mouse.up();

    await adjustScreenView(page);

    await zoomOut(page, 4);

    await page.getByTestId("more-options-modal").click();

    await page.waitForSelector('[data-testid="minimize-button-modal"]', {
      timeout: 10000,
    });

    await page.getByTestId("minimize-button-modal").first().click();

    await expect(
      page.locator(".react-flow__handle-left.no-show").first(),
    ).toBeVisible({ timeout: 10000 });

    await expect(
      page.locator(".react-flow__handle-right.no-show").first(),
    ).toBeVisible({ timeout: 10000 });

    await page.getByTestId("more-options-modal").click();

    await page.waitForSelector('[data-testid="expand-button-modal"]', {
      timeout: 10000,
    });

    await page.getByTestId("expand-button-modal").first().click();

    await expect(page.locator(".react-flow__handle-left").first()).toBeVisible({
      timeout: 10000,
    });

    await expect(page.locator(".react-flow__handle-right").first()).toBeVisible(
      { timeout: 10000 },
    );
  },
);
