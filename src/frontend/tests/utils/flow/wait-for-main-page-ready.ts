import { expect, type Page } from "@playwright/test";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

/**
 * Wait for the main page header to belong to the route we just navigated to.
 *
 * react-router v7 defers route render, so for a beat after a navigation the
 * outgoing page is still mounted — and it has a mainpage_title of its own.
 * A bare `waitForSelector` therefore resolves against the page being torn
 * down, and a one-shot `textContent()` read returns *its* heading. Passing
 * the expected `title` pins the wait to the new route with a retrying
 * matcher; omit it when any main page will do.
 *
 * The default expect timeout (5s) is also too tight for a full `goto("/")`,
 * which reboots the app, so this waits up to TIMEOUTS.standard.
 */
export async function waitForMainPageReady(
  page: Page,
  title?: string,
): Promise<void> {
  const heading = page.getByTestId(TID.mainpageTitle);
  if (title === undefined) {
    await expect(heading).toBeVisible({ timeout: TIMEOUTS.standard });
    return;
  }
  await expect(heading).toContainText(title, { timeout: TIMEOUTS.standard });
}
