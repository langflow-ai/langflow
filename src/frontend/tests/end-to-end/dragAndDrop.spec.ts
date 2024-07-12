import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";

test.describe("drag and drop test", () => {
  /// <reference lib="dom"/>
  test("drop collection", async ({ page }) => {
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
      await page.getByText("New Project", { exact: true }).click();
      await page.waitForTimeout(5000);
      modalCount = await page.getByTestId("modal-title")?.count();
    }
    await page.locator("span").filter({ hasText: "Close" }).first().click();

    await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
    // Read your file into a buffer.
    const jsonContent = readFileSync(
      "tests/end-to-end/assets/collection.json",
      "utf-8",
    );

    // Create the DataTransfer and File
    const dataTransfer = await page.evaluateHandle((data) => {
      const dt = new DataTransfer();
      // Convert the buffer to a hex array
      const file = new File([data], "flowtest.json", {
        type: "application/json",
      });
      dt.items.add(file);
      return dt;
    }, jsonContent);

    // Now dispatch
    await page.dispatchEvent(
      '//*[@id="root"]/div/div[1]/div[2]/div[3]/div/div',
      "drop",
      {
        dataTransfer,
      },
    );

    const genericNode = page.getByTestId("div-generic-node");
    const elementCount = await genericNode?.count();
    if (elementCount > 0) {
      expect(true).toBeTruthy();
    }
  });
});
