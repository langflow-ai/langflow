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

  // Wait for the dropped flow ("Memory Chatbot") to appear in the list.
  // Bootstrap pre-seeds a "Basic Prompting" flow, so waiting on the generic
  // list-card selector races with the upload and can pick the wrong card.
  const droppedFlowCard = page
    .getByTestId("list-card")
    .filter({ hasText: "Memory Chatbot" })
    .first();
  await droppedFlowCard.waitFor({ state: "visible", timeout: 30000 });
  await droppedFlowCard.click();

  // Verify the outdated components banner appears on the canvas
  await expect(page.getByText("Updates are available for 5")).toBeVisible({
    timeout: 30000,
  });
});
