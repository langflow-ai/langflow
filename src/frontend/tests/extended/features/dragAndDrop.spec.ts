import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
test(
  "user should be able to drag and drop an old collection without crashing the application",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.locator("span").filter({ hasText: "Close" }).first().click();

    await page.locator("span").filter({ hasText: "My Projects" }).isVisible();
    // Read your file into a buffer.
    const jsonContent = readFileSync("tests/assets/collection.json", "utf-8");

    // Create DataTransfer object with file
    const dataTransfer = await page.evaluateHandle(async (content) => {
      const dt = new DataTransfer();
      const file = new File([content], "collection.json", {
        type: "application/json",
      });
      dt.items.add(file);
      return dt;
    }, jsonContent);

    await page.getByTestId("cards-wrapper").dispatchEvent("drop", {
      dataTransfer,
    });

    await page.waitForSelector("text=uploaded successfully", {
      timeout: 60000 * 2,
    });

    const genericNode = page.getByTestId("div-generic-node");
    const elementCount = await genericNode?.count();
    if (elementCount > 0) {
      expect(true).toBeTruthy();
    }

    await page.waitForSelector("text=Getting Started:", {
      timeout: 100000,
    });

    expect(
      await page.locator("text=Getting Started:").last().isVisible(),
    ).toBeTruthy();
  },
);

test(
  "user should be able to drag and drop a flow on main page",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.locator("span").filter({ hasText: "Close" }).first().click();
    await page.locator("span").filter({ hasText: "My Projects" }).isVisible();

    // Read your file into a buffer.
    const jsonContent = readFileSync(
      "tests/assets/flow_test_drag_and_drop.json",
      "utf-8",
    );

    const randomName = Math.random().toString(36).substring(2, 15);
    const jsonContentWithNewName = jsonContent.replace(
      "LANGFLOW TEST",
      randomName,
    );

    // Create DataTransfer object with file
    const dataTransfer = await page.evaluateHandle(async (content) => {
      const dt = new DataTransfer();
      const file = new File([content], "flow_test_drag_and_drop.json", {
        type: "application/json",
      });
      dt.items.add(file);
      return dt;
    }, jsonContentWithNewName);

    await page.getByTestId("cards-wrapper").dispatchEvent("drop", {
      dataTransfer,
    });

    await page.waitForSelector("text=uploaded successfully", {
      timeout: 60000 * 2,
    });

    const genericNode = page.getByTestId("div-generic-node");

    const elementCount = await genericNode?.count();
    if (elementCount > 0) {
      expect(true).toBeTruthy();
    }

    await page.waitForSelector(`text=${randomName}`, {
      timeout: 100000,
    });

    expect(
      await page.locator(`text=${randomName}`).last().isVisible(),
    ).toBeTruthy();
  },
);
