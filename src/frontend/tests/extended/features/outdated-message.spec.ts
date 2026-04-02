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

  await page.waitForSelector("data-testid=list-card", {
    timeout: 3000,
  });

  await page.getByTestId("list-card").first().click();

  // The api_key field may show a global variable badge instead of an input
  // when OPENAI_API_KEY is in the environment. Either way, we just need to
  // trigger a run to get the outdated components error message.
  const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
  if (await apiKeyInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await apiKeyInput.fill("this is a test to crash");
  }

  await page.getByTestId("button_run_chat output").click();

  await expect(
    page.getByText("there are outdated components in the flow"),
  ).toBeVisible({ timeout: 30000 });
});
