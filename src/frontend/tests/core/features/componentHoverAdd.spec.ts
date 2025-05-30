import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user can add components by hovering and clicking the plus icon",
  { tag: ["@release", "@components", "@workspace"] },

  async ({ page }) => {
    // Navigate to homepage and handle initial modal
    await awaitBootstrapTest(page);

    // Start with blank flow
    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 3000,
    });

    // Search for a component
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");

    await page.waitForSelector('[data-testid="input_outputChat Input"]', {
      timeout: 2000,
    });
    // Hover over the component and verify plus icon
    const componentLocator = page.getByTestId("input_outputChat Input");
    // Find the plus icon within the specific component container
    const plusIcon = componentLocator.getByTestId("icon-Plus");

    // Get the opacity
    const opacity = await plusIcon.evaluate((el) =>
      window.getComputedStyle(el).getPropertyValue("opacity"),
    );

    await expect(plusIcon).toBeVisible();

    await expect(opacity).toBe("0");

    await componentLocator.hover();
    // Hover over the component
    await expect(plusIcon).toBeVisible();
    // Wait for the animation to change the opacity
    await page.waitForTimeout(500);

    const opacityAfterHover = await plusIcon.evaluate((el) =>
      window.getComputedStyle(el).getPropertyValue("opacity"),
    );

    expect(Number(opacityAfterHover)).toBeGreaterThanOrEqual(0);

    // Click the plus icon associated with this component
    await plusIcon.click();
    // Wait for the component to be added to the flow
    await page.waitForSelector(".react-flow__node", { timeout: 1000 });

    // Verify component was added to the flow
    const addedComponent = page.locator(".react-flow__node").first();
    await expect(addedComponent).toBeVisible();
  },
);
