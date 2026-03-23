import type { Locator } from "@playwright/test";
import { expect } from "../fixtures";

/**
 * Ensures a checkbox reaches the "checked" state.
 * On Windows CI, auto-select after upload may not trigger due to a race
 * condition between focus/change events. This helper clicks the checkbox
 * manually if it's not auto-checked within the initial timeout.
 */
export async function ensureCheckboxChecked(checkbox: Locator, timeout = 5000) {
  try {
    await expect(checkbox).toHaveAttribute("data-state", "checked", {
      timeout,
    });
  } catch {
    await checkbox.click();
    await expect(checkbox).toHaveAttribute("data-state", "checked", {
      timeout: 3000,
    });
  }
}
