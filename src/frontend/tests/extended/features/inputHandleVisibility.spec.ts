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

    const COLLAPSED_SIZE = "5px";
    const EXPANDED_SIZE = "10px";
    const widthOf = () => inputDot.evaluate((el) => getComputedStyle(el).width);

    // Deselect the freshly-dropped node by clicking empty canvas.
    await page
      .locator(".react-flow__pane")
      .click({ position: { x: 50, y: 50 } });

    // Default: input handle dot is small (collapsed) but still visible.
    await expect.poll(widthOf, { timeout: 10000 }).toBe(COLLAPSED_SIZE);

    // Selecting the node grows the input handle to full size.
    await page.getByTestId("title-Chat Output").first().click();
    await expect.poll(widthOf, { timeout: 10000 }).toBe(EXPANDED_SIZE);

    // Deselect again — back to the small collapsed size.
    await page
      .locator(".react-flow__pane")
      .click({ position: { x: 50, y: 50 } });
    await expect.poll(widthOf, { timeout: 10000 }).toBe(COLLAPSED_SIZE);

    // Hovering the handle hitbox grows the dot to full size.
    await inputHandle.hover();
    await expect.poll(widthOf, { timeout: 10000 }).toBe(EXPANDED_SIZE);
  },
);
