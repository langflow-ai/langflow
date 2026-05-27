import { readFileSync } from "fs";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test("user must be able outdated message on error", async ({ page }) => {
  await awaitBootstrapTest(page);

  await page.locator("span").filter({ hasText: "Close" }).first().click();

  await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
  // Read your file into a buffer.
  const jsonContent = readFileSync("tests/assets/outdated_flow.json", "utf-8");

  // Create the DataTransfer and File
  const dataTransfer = await page.evaluateHandle((data) => {
    const dt = new DataTransfer();
    // Convert the buffer to a hex array
    const file = new File([data], "outdated_flow.json", {
      type: "application/json",
    });
    dt.items.add(file);
    return dt;
  }, jsonContent);

  // Now dispatch
  await page.getByTestId("cards-wrapper").dispatchEvent("drop", {
    dataTransfer,
  });

  // Wait for the upload-complete toast before clicking — bootstrap pre-seeds a
  // "Basic Prompting" flow, so racing the generic list-card selector picks the
  // wrong card before the dropped flow appears in the refetched list.
  await expect(page.getByText("All files uploaded successfully")).toBeVisible({
    timeout: 30000,
  });

  // List is sorted by updated_at DESC, so the newest (just-dropped) card is first.
  await page.getByTestId("list-card").first().click();

  // Verify the outdated components banner appears on the canvas
  await expect(page.getByText("Updates are available for 5")).toBeVisible({
    timeout: 30000,
  });
});
