import { type Page } from "@playwright/test";

/**
 * Dismiss every visible "Legacy" warning bar on the canvas.
 *
 * Legacy components render a warning bar at the top of their node, which
 * increases the node's height. In tightly-packed test layouts that extra
 * height can push a node's bar/body over an adjacent node's handle or button
 * and intercept clicks. Dismissing the bars restores the compact, pre-legacy
 * layout the tests were written against so the real click lands on its target.
 */
export async function dismissLegacyWarnings(page: Page): Promise<void> {
  const bars = page.getByTestId("dismiss-warning-bar");
  // There are only ever a handful of legacy nodes; cap iterations as a guard.
  for (let i = 0; i < 12; i++) {
    if ((await bars.count()) === 0) {
      break;
    }
    await bars.first().click();
    // Allow the dismissal to remove the bar before re-counting.
    await page.waitForTimeout(200);
  }
}
