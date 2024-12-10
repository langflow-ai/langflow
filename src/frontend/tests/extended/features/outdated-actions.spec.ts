import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test("user must be able to update outdated components", async ({ page }) => {
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

  await page.waitForSelector("data-testid=list-card", {
    timeout: 3000,
  });

  await page.getByTestId("list-card").first().click();

  await expect(page.getByText("components are ready to update")).toBeVisible({
    timeout: 30000,
  });

  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  expect(outdatedComponents).toBeGreaterThan(0);

  await page.getByText("Update All", { exact: true }).click();

  await expect(page.getByTestId("icon-AlertTriangle")).toHaveCount(0, {
    timeout: 5000,
  });
});
