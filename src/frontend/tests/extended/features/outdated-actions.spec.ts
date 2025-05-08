import { expect, test } from "@playwright/test";
import { readFileSync } from "fs";
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

  let outdatedComponents = await page.getByTestId("update-button").count();
  expect(outdatedComponents).toBe(1);

  let outdatedBreakingComponents = await page
    .getByTestId("review-button")
    .count();
  expect(outdatedBreakingComponents).toBe(4);

  expect(await page.getByTestId("update-all-button")).toHaveText("Review All");

  await page.getByTestId("update-all-button").click();

  expect(
    await page.locator('input[data-ref="eInput"]').nth(2).isChecked(),
  ).toBe(false);

  expect(
    await page.locator('input[data-ref="eInput"]').nth(3).isChecked(),
  ).toBe(false);

  expect(
    await page.locator('input[data-ref="eInput"]').nth(4).isChecked(),
  ).toBe(true);

  expect(
    await page.locator('input[data-ref="eInput"]').nth(5).isChecked(),
  ).toBe(false);

  expect(
    await page.locator('input[data-ref="eInput"]').nth(6).isChecked(),
  ).toBe(false);

  await page
    .getByRole("checkbox", { name: "Column with Header Selection" })
    .check();

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

  let outdatedComponents = await page.getByTestId("update-button").count();
  expect(outdatedComponents).toBe(1);

  let outdatedBreakingComponents = await page
    .getByTestId("review-button")
    .count();
  expect(outdatedBreakingComponents).toBe(4);

  expect(await page.getByTestId("update-all-button")).toHaveText("Review All");

  await page.getByTestId("review-button").first().click();

  await page.waitForSelector("button[data-testid='backup-flow-checkbox']", {
    timeout: 30000,
  });

  expect(await page.getByTestId("backup-flow-checkbox").isChecked()).toBe(true);

  await page.getByRole("button", { name: "Update Component" }).click();

  await expect(page.getByTestId("update-button")).toHaveCount(1, {
    timeout: 5000,
  });

  await expect(page.getByTestId("review-button")).toHaveCount(3, {
    timeout: 5000,
  });

  await expect(page.getByText("Updates are available for 4")).toBeVisible({
    timeout: 30000,
  });

  expect(await page.getByTestId("update-all-button")).toHaveText("Review All");

  await page.getByTestId("update-button").first().click();

  await expect(page.getByTestId("update-button")).toHaveCount(0, {
    timeout: 5000,
  });

  await expect(page.getByTestId("review-button")).toHaveCount(3, {
    timeout: 5000,
  });

  await awaitBootstrapTest(page, { skipModal: true });

  await expect(page.getByText("Backup").count()).toBeGreaterThan(0);
});
