import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { simulateDragAndDrop } from "../../utils/simulate-drag-and-drop";
test(
  "user should be able to drag and drop an old collection without crashing the application",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    //add a new flow just to have the workspace available
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector("text=starter project", {
      timeout: 5000,
    });

    await page.waitForSelector('[data-testid="new-project-btn"]', {
      timeout: 100000,
    });

    await simulateDragAndDrop(
      page,
      "tests/assets/collection.json",
      "cards-wrapper",
    );

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

    //add a new flow just to have the workspace available
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector("text=starter project", {
      timeout: 5000,
    });

    await page.waitForSelector('[data-testid="new-project-btn"]', {
      timeout: 100000,
    });
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

    await simulateDragAndDrop(
      page,
      "tests/assets/flow_test_drag_and_drop.json",
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
