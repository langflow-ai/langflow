import { readFileSync } from "fs";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test("user must be able to update outdated components by update all button", async ({
  page,
}) => {
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

  await page.waitForTimeout(1000);

  await page.waitForSelector("data-testid=list-card", {
    timeout: 3000,
  });

  await page.getByTestId("list-card").first().click();

  await expect(page.getByText("Updates are available for 5")).toBeVisible({
    timeout: 30000,
  });

  const outdatedComponents = await page.getByTestId("update-button").count();
  expect(outdatedComponents).toBe(0);

  const outdatedBreakingComponents = await page
    .getByTestId("review-button")
    .count();
  expect(outdatedBreakingComponents).toBe(5);

  expect(await page.getByTestId("update-all-button")).toHaveText("Review All");

  await page.getByTestId("update-all-button").click();

  // Verify all component checkboxes start unchecked (indices 2..6 for 5 components)
  for (let i = 2; i <= 6; i++) {
    expect(
      await page.locator('input[data-ref="eInput"]').nth(i).isChecked(),
    ).toBe(false);
  }

  await page
    .getByRole("checkbox", { name: "Column with Header Selection" })
    .check();

  // Verify all component checkboxes are now checked
  for (let i = 2; i <= 6; i++) {
    expect(
      await page.locator('input[data-ref="eInput"]').nth(i).isChecked(),
    ).toBe(true);
  }

  expect(await page.getByTestId("backup-flow-checkbox").isChecked()).toBe(true);
  await page.getByTestId("backup-flow-checkbox").click();

  await page.getByRole("button", { name: "Update Components" }).click();

  await expect(page.getByTestId("update-button")).toHaveCount(0, {
    timeout: 5000,
  });

  await expect(page.getByTestId("review-button")).toHaveCount(0, {
    timeout: 5000,
  });
});

test("user must be able to update outdated components by each outdated component", async ({
  page,
}) => {
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

  await page.waitForTimeout(1000);

  await page.waitForSelector("data-testid=list-card", {
    timeout: 3000,
  });

  await page.getByTestId("list-card").first().click();

  await expect(page.getByText("Updates are available for 5")).toBeVisible({
    timeout: 30000,
  });

  const outdatedComponents = await page.getByTestId("update-button").count();
  expect(outdatedComponents).toBe(0);

  const outdatedBreakingComponents = await page
    .getByTestId("review-button")
    .count();
  expect(outdatedBreakingComponents).toBe(5);

  expect(await page.getByTestId("update-all-button")).toHaveText("Review All");

  await page.getByTestId("review-button").first().click();

  await page.waitForSelector("button[data-testid='backup-flow-checkbox']", {
    timeout: 30000,
  });

  expect(await page.getByTestId("backup-flow-checkbox").isChecked()).toBe(true);

  await page.getByRole("button", { name: "Update Component" }).click();

  await expect(page.getByTestId("update-button")).toHaveCount(0, {
    timeout: 5000,
  });

  await expect(page.getByTestId("review-button")).toHaveCount(4, {
    timeout: 5000,
  });

  await expect(page.getByText("Updates are available for 4")).toBeVisible({
    timeout: 30000,
  });

  expect(await page.getByTestId("update-all-button")).toHaveText("Review All");

  await awaitBootstrapTest(page, { skipModal: true });

  expect(await page.getByText("Backup").count()).toBeGreaterThan(0);
});
