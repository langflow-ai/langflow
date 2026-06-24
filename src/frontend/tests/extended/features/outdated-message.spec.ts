import { readFileSync } from "fs";
import { expect, test } from "../../fixtures";
import { openFlowsList } from "../../utils/flow/open-flows-list";

test("user must be able outdated message on error", async ({ page }) => {
  const dropTarget = await openFlowsList(page);

  await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
  // Read the asset and rename the flow uniquely so we can wait for THIS
  // upload to appear in the list — avoids racing against the bootstrap-seeded
  // "Basic Prompting" card or stale "Memory Chatbot" entries from sibling tests.
  const rawJson = readFileSync("tests/assets/outdated_flow.json", "utf-8");
  const flowName = `Outdated Test Flow ${Date.now()}`;
  const jsonContent = JSON.stringify({
    ...JSON.parse(rawJson),
    name: flowName,
  });

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
  await dropTarget.dispatchEvent("drop", {
    dataTransfer,
  });

  // Wait for the freshly-dropped flow card (by unique name) to appear, then click it.
  const droppedCard = page
    .getByTestId("list-card")
    .filter({ hasText: flowName });
  await droppedCard.waitFor({ state: "visible", timeout: 30000 });
  await droppedCard.click();

  // Verify the outdated components banner appears on the canvas.
  await expect(page.getByText(/\d+ components? needs? updates?/)).toBeVisible({
    timeout: 30000,
  });
});
