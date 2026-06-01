import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

/**
 * Input (target) handles render as a small collapsed dot by default and grow
 * to full size when the node is selected or the handle itself is hovered
 * (connected/drag states are covered by unit tests on
 * `isInputHandleCollapsed`). Output handles are not affected by this rule.
 */
test(
  "input handle is small by default and grows on selection and hover",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      state: "visible",
    });
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill(TEXTS.searchChatOutput);
    await page.waitForSelector('[data-testid="input_outputChat Output"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("input_outputChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 300 },
      });

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await adjustScreenView(page);

    // The visible dot lives in a child div; the 32px hitbox is the wrapper.
    const inputDot = page
      .locator('[data-testid^="div-handle-chatoutput"][data-testid$="-target"]')
      .first();
    const inputHandle = page
      .locator('[data-testid^="handle-chatoutput"][data-testid$="-target"]')
      .first();

    await inputDot.waitFor({ state: "attached", timeout: 30000 });

    const COLLAPSED_WIDTH = 5;
    const EXPANDED_WIDTH = 10;
    // offsetWidth is the border-box width, robust to box-sizing/border.
    const widthOf = () =>
      inputDot.evaluate((el) => (el as HTMLElement).offsetWidth);
    const shadowOf = () =>
      inputDot.evaluate((el) => getComputedStyle(el).boxShadow);
    const backgroundOf = () =>
      inputDot.evaluate((el) => getComputedStyle(el).backgroundColor);

    // Deselect the freshly-dropped node by clicking empty canvas.
    await page
      .locator(".react-flow__pane")
      .click({ position: { x: 50, y: 50 } });

    // Default: small, colorless (gray) and without the neon ring/glow.
    await expect.poll(widthOf, { timeout: 10000 }).toBe(COLLAPSED_WIDTH);
    await expect.poll(shadowOf, { timeout: 10000 }).toBe("none");
    const collapsedBackground = await backgroundOf();

    // Selecting the node grows it to full size, gives it the datatype color
    // and the neon ring.
    await page.getByTestId("title-Chat Output").first().click();
    await expect.poll(widthOf, { timeout: 10000 }).toBe(EXPANDED_WIDTH);
    await expect.poll(shadowOf, { timeout: 10000 }).not.toBe("none");
    expect(await backgroundOf()).not.toBe(collapsedBackground);

    // Deselect again — back to the small colorless collapsed state.
    await page
      .locator(".react-flow__pane")
      .click({ position: { x: 50, y: 50 } });
    await expect.poll(widthOf, { timeout: 10000 }).toBe(COLLAPSED_WIDTH);
    await expect
      .poll(backgroundOf, { timeout: 10000 })
      .toBe(collapsedBackground);

    // Hovering the handle hitbox grows it and brings back its color/glow.
    await inputHandle.hover();
    await expect.poll(widthOf, { timeout: 10000 }).toBe(EXPANDED_WIDTH);
    await expect.poll(shadowOf, { timeout: 10000 }).not.toBe("none");
  },
);
