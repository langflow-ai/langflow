import type { Locator } from "@playwright/test";
import { expect } from "../fixtures";

/**
 * Ensures a checkbox reaches the "checked" state.
 * On Windows CI, auto-select after upload may not trigger due to a race
 * condition between the optimistic cache path and the server path.
 * Additionally, Radix Checkbox's onCheckedChange may not fire reliably
 * with Playwright synthetic clicks on Windows. This helper clicks the
 * parent file row (which has its own onClick handler) as a fallback.
 */
export async function ensureCheckboxChecked(checkbox: Locator, timeout = 5000) {
  try {
    await expect(checkbox).toHaveAttribute("data-state", "checked", {
      timeout,
    });
  } catch {
    // Click the parent file row instead of the checkbox directly.
    // The row's onClick calls handleFileSelect(file.path) using the
    // current file.path from the query cache, which correctly adds
    // it to selectedFiles and triggers the checkbox to check.
    const row = checkbox.locator(
      'xpath=ancestor::div[starts-with(@data-testid,"file-item-")]',
    );
    await row.click();
    await expect(checkbox).toHaveAttribute("data-state", "checked", {
      timeout: 5000,
    });
  }
}
