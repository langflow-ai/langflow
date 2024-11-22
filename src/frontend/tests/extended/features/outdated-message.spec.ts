import { test } from "@playwright/test";
import { readFileSync } from "fs";

test("user must be able outdated message on error", async ({ page }) => {
  await page.goto("/");

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }
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

  await page.waitForTimeout(3000);

  await page.getByTestId("list-card").first().click();

  await page
    .getByTestId("popover-anchor-input-api_key")
    .fill("this is a test to crash");

  await page.getByTestId("button_run_chat output").click();

  await page.waitForSelector("text=there are outdated components in the flow", {
    timeout: 30000,
    state: "visible",
  });
});
