import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";
import { simulateDragAndDrop } from "../../utils/simulate-drag-and-drop";
test(
  "user should be able to drag and drop an old collection without crashing the application",
  { tag: ["@release"] },
  async ({ page }) => {
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
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    await page.locator("span").filter({ hasText: "Close" }).first().click();

    await page.locator("span").filter({ hasText: "My Projects" }).isVisible();

    await simulateDragAndDrop(page, "assets/collection.json", "cards-wrapper");

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
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    await page.locator("span").filter({ hasText: "Close" }).first().click();
    await page.locator("span").filter({ hasText: "My Projects" }).isVisible();

    // Read your file into a buffer.
    const jsonContent = readFileSync(
      "assets/flow_test_drag_and_drop.json",
      "utf-8",
    );

    const randomName = Math.random().toString(36).substring(2, 15);
    const jsonContentWithNewName = jsonContent.replace(
      "LANGFLOW TEST",
      randomName,
    );

    await simulateDragAndDrop(
      page,
      "assets/flow_test_drag_and_drop.json",
      "cards-wrapper",
      jsonContentWithNewName,
    );

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
