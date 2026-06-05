import { readFileSync } from "fs";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test("user must be able outdated message on error", async ({ page }) => {
  // `skipModal: true` keeps us on the home page (cards-wrapper lives here).
  // Without it, openTemplatesModal navigates to a fresh canvas + FlowBuilderWelcome
  // overlay, so closing the modal leaves the user on the canvas and the
  // drag-and-drop target below never appears.
  await awaitBootstrapTest(page, { skipModal: true });

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
  await page.getByTestId("cards-wrapper").dispatchEvent("drop", {
    dataTransfer,
  });

  // Wait for the freshly-dropped flow card (by unique name) to appear, then click it.
  const droppedCard = page
    .getByTestId("list-card")
    .filter({ hasText: flowName });
  await droppedCard.waitFor({ state: "visible", timeout: 30000 });
  await droppedCard.click();

  // Verify the outdated components banner appears on the canvas
  await expect(page.getByText("5 components need updates")).toBeVisible({
    timeout: 30000,
  });
});
