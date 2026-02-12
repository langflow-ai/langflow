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

  await page.getByText("Memory Chatbot").first().waitFor({ timeout: 5000 });

  await page.getByText("Memory Chatbot").first().click();

  // Wait for the canvas to render the flow nodes
  await page.getByTestId("button_run_chat output").waitFor({ timeout: 10000 });

  await page.getByTestId("button_run_chat output").click();

  await expect(
    page.getByText("there are outdated components in the flow"),
  ).toBeVisible({ timeout: 60000 });
});
