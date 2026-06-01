import { readFileSync } from "fs";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test("user must be able to update outdated components by update all button", async ({
  page,
}) => {
  // `skipModal: true` keeps us on the home page (cards-wrapper lives here).
  // Without it, openTemplatesModal navigates to a fresh canvas + FlowBuilderWelcome
  // overlay, so closing the modal leaves the user on the canvas and the
  // drag-and-drop target below never appears.
  await awaitBootstrapTest(page, { skipModal: true });

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
  await page.getByTestId("cards-wrapper").dispatchEvent("drop", {
    dataTransfer,
  });

  // Wait for the freshly-dropped flow card (by unique name) to appear, then click it.
  const droppedCard = page
    .getByTestId("list-card")
    .filter({ hasText: flowName });
  await droppedCard.waitFor({ state: "visible", timeout: 30000 });
  await droppedCard.click();

  await expect(page.getByText("5 components need updates")).toBeVisible({
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

  await expect(page.getByTestId("backup-flow-checkbox")).toBeChecked();
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
  // `skipModal: true` keeps us on the home page (cards-wrapper lives here).
  // Without it, openTemplatesModal navigates to a fresh canvas + FlowBuilderWelcome
  // overlay, so closing the modal leaves the user on the canvas and the
  // drag-and-drop target below never appears.
  await awaitBootstrapTest(page, { skipModal: true });

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
  await page.getByTestId("cards-wrapper").dispatchEvent("drop", {
    dataTransfer,
  });

  // Wait for the freshly-dropped flow card (by unique name) to appear, then click it.
  const droppedCard = page
    .getByTestId("list-card")
    .filter({ hasText: flowName });
  await droppedCard.waitFor({ state: "visible", timeout: 30000 });
  await droppedCard.click();

  await expect(page.getByText("5 components need updates")).toBeVisible({
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

  await expect(page.getByTestId("backup-flow-checkbox")).toBeChecked();

  await page.getByRole("button", { name: "Update Component" }).click();

  await expect(page.getByTestId("update-button")).toHaveCount(0, {
    timeout: 5000,
  });

  await expect(page.getByTestId("review-button")).toHaveCount(4, {
    timeout: 5000,
  });

  await expect(page.getByText("4 components need updates")).toBeVisible({
    timeout: 30000,
  });

  expect(await page.getByTestId("update-all-button")).toHaveText("Review All");

  await awaitBootstrapTest(page, { skipModal: true });

  expect(await page.getByText("Backup").count()).toBeGreaterThan(0);
});
