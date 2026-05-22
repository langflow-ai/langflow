import type { Locator, Page } from "@playwright/test";
import { SELECTORS, TID } from "../constants/testIds";

/**
 * Resolve the "..." more-menu button for a session in the playground sidebar.
 *
 * The sidebar uses pattern test-ids like `session-<uuid>-more-menu`, so
 * specs typically pick the first or last match.
 */
export function sessionMoreMenu(
  page: Page,
  position: "first" | "last" = "first",
): Locator {
  const locator = page.locator(SELECTORS.sessionMoreMenuPattern);
  return position === "first" ? locator.first() : locator.last();
}

/** Convenience: the session-selector chip on a chat row. */
export function sessionSelector(page: Page): Locator {
  return page.getByTestId(TID.sessionSelector);
}
