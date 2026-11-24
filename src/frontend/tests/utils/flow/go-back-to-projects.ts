import type { Page } from "@playwright/test";
import { TID } from "../constants/testIds";

/**
 * Click the back chevron to return from a flow editor to the projects page.
 *
 * Both `.first()` and `.last()` are seen in existing specs because some
 * pages render extra chevrons in the header. The default uses `.first()`
 * (matches the majority of call sites); pass `last: true` for the
 * legacy MCP / auto-save patterns.
 */
export async function goBackToProjects(
  page: Page,
  options?: { last?: boolean },
): Promise<void> {
  const chevron = page.getByTestId(TID.iconChevronLeft);
  if (options?.last) {
    await chevron.last().click();
  } else {
    await chevron.first().click();
  }
}
