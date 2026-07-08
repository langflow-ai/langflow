import { readFileSync } from "fs";
import { expect, test } from "../../fixtures";
import { openFlowsList } from "../../utils/flow/open-flows-list";

test.describe.configure({ mode: "serial" });

test(
  "user must be able to update outdated components by update all button",
  { tag: ["@release"] },
  async ({ page }) => {
    const dropTarget = await openFlowsList(page);

    await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
    // Read the asset and rename the flow uniquely so we can wait for THIS
    // upload to appear in the list — avoids racing against the bootstrap-seeded
    // "Basic Prompting" card or stale "Memory Chatbot" entries from sibling tests.
    const rawJson = readFileSync("tests/assets/outdated_flow.json", "utf-8");
    const flowName = `Outdated Test Flow ${Date.now()}-${Math.random()
      .toString(36)
      .slice(2, 8)}`;
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

    await expect(page.getByText(/\d+ components? needs? updates?/)).toBeVisible(
      {
        timeout: 30000,
      },
    );

    const outdatedComponents = await page.getByTestId("update-button").count();
    expect(outdatedComponents).toBe(0);

    const outdatedBreakingComponents = await page
      .getByTestId("review-button")
      .count();
    expect(outdatedBreakingComponents).toBeGreaterThan(0);

    expect(await page.getByTestId("update-all-button")).toHaveText(
      "Review All",
    );

    await page.getByTestId("update-all-button").click();

    // Verify all component checkboxes start unchecked.
    for (let i = 2; i < 2 + outdatedBreakingComponents; i++) {
      expect(
        await page.locator('input[data-ref="eInput"]').nth(i).isChecked(),
      ).toBe(false);
    }

    await page
      .getByRole("checkbox", { name: "Column with Header Selection" })
      .check();

    // Verify all component checkboxes are now checked.
    for (let i = 2; i < 2 + outdatedBreakingComponents; i++) {
      expect(
        await page.locator('input[data-ref="eInput"]').nth(i).isChecked(),
      ).toBe(true);
    }

    await expect(page.getByTestId("backup-flow-checkbox")).toBeChecked();
    await page.getByTestId("backup-flow-checkbox").click();

    await page.getByRole("button", { name: "Update Components" }).click();

    await expect(page.getByTestId("update-button")).toHaveCount(0, {
      timeout: 5000,
    });

    await expect(page.getByTestId("review-button")).toHaveCount(0, {
      timeout: 5000,
    });
  },
);

test(
  "user must be able to update outdated components by each outdated component",
  { tag: ["@release"] },
  async ({ page }) => {
    const dropTarget = await openFlowsList(page);

    await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
    // Read the asset and rename the flow uniquely so we can wait for THIS
    // upload to appear in the list — avoids racing against the bootstrap-seeded
    // "Basic Prompting" card or stale "Memory Chatbot" entries from sibling tests.
    const rawJson = readFileSync("tests/assets/outdated_flow.json", "utf-8");
    const flowName = `Outdated Test Flow ${Date.now()}-${Math.random()
      .toString(36)
      .slice(2, 8)}`;
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

    await expect(page.getByText(/\d+ components? needs? updates?/)).toBeVisible(
      {
        timeout: 30000,
      },
    );

    const outdatedComponents = await page.getByTestId("update-button").count();
    expect(outdatedComponents).toBe(0);

    const outdatedBreakingComponents = await page
      .getByTestId("review-button")
      .count();
    expect(outdatedBreakingComponents).toBeGreaterThan(0);

    expect(await page.getByTestId("update-all-button")).toHaveText(
      "Review All",
    );

    await page.getByTestId("review-button").first().click();

    await page.waitForSelector("button[data-testid='backup-flow-checkbox']", {
      timeout: 30000,
    });

    await expect(page.getByTestId("backup-flow-checkbox")).toBeChecked();

    await page.getByRole("button", { name: "Update Component" }).click();

    await expect(page.getByTestId("update-button")).toHaveCount(0, {
      timeout: 5000,
    });

    await expect(page.getByTestId("review-button")).toHaveCount(
      outdatedBreakingComponents - 1,
      {
        timeout: 5000,
      },
    );

    await expect(page.getByText(/\d+ components? needs? updates?/)).toBeVisible(
      {
        timeout: 5000,
      },
    );

    expect(await page.getByTestId("update-all-button")).toHaveText(
      "Review All",
    );

    await openFlowsList(page);

    expect(await page.getByText("Backup").count()).toBeGreaterThan(0);
  },
);
