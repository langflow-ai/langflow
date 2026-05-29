import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

/**
 * Input (target) handles are invisible by default and only revealed when the
 * node is selected or the handle itself is hovered (connected/drag states are
 * covered by unit tests on `isInputHandleHidden`). Output handles are not
 * affected by this rule.
 */
test(
  "input handle is invisible by default and revealed on selection and hover",
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

    const opacityOf = () =>
      inputDot.evaluate((el) => getComputedStyle(el).opacity);

    // Deselect the freshly-dropped node by clicking empty canvas.
    await page.locator(".react-flow__pane").click({ position: { x: 50, y: 50 } });

    // Default: input handle dot is invisible.
    await expect.poll(opacityOf, { timeout: 10000 }).toBe("0");

    // Selecting the node reveals the input handle.
    await page.getByTestId("title-Chat Output").first().click();
    await expect.poll(opacityOf, { timeout: 10000 }).toBe("1");

    // Deselect again — back to invisible.
    await page.locator(".react-flow__pane").click({ position: { x: 50, y: 50 } });
    await expect.poll(opacityOf, { timeout: 10000 }).toBe("0");

    // Hovering the handle hitbox reveals the dot.
    await inputHandle.hover();
    await expect.poll(opacityOf, { timeout: 10000 }).toBe("1");
  },
);
