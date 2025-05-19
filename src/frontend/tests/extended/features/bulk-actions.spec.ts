import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to select flows with different methods and perform bulk actions",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Add some flows to test with
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await adjustScreenView(page);

    // Go back to main page
    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });
    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.getByText("Projects").first().isVisible();
    await page.getByText("New Flow", { exact: true }).click();
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Document Q&A" }).click();
    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });
    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.getByText("Projects").first().isVisible();
    await page.getByText("New Flow", { exact: true }).click();
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });
    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.getByText("Projects").first().isVisible();
    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 100000,
    });
    await page.getByTestId("list-card").first().isVisible({ timeout: 3000 });
    await page.waitForTimeout(500);

    // Test shift selection
    await page.keyboard.down("Shift");
    await page.getByTestId("list-card").first().click();
    await page.getByTestId("list-card").nth(2).click();
    await page.keyboard.up("Shift");

    // Verify both flows are selected
    const firstCheckbox = await page.getByTestId(/^checkbox-/).first();
    const secondCheckbox = await page.getByTestId(/^checkbox-/).nth(1);
    const thirdCheckbox = await page.getByTestId(/^checkbox-/).nth(2);
    await expect(firstCheckbox).toBeChecked();
    await expect(secondCheckbox).toBeChecked();
    await expect(thirdCheckbox).toBeChecked();
    // Test bulk download
    await page.getByTestId("download-bulk-btn").last().click();
    await expect(page.getByText(/.*downloaded successfully/)).toBeVisible({
      timeout: 10000,
    });

    // Deselect all
    await page.keyboard.down("Shift");
    await page.getByTestId("list-card").first().click();
    await page.keyboard.up("Shift");

    // Verify both flows are deselected
    await expect(firstCheckbox).not.toBeChecked();
    await expect(secondCheckbox).not.toBeChecked();
    await expect(thirdCheckbox).not.toBeChecked();

    // Test Ctrl/Cmd selection
    await page.keyboard.down("ControlOrMeta");
    await page.getByTestId("list-card").first().click();
    await page.getByTestId("list-card").nth(2).click();
    await page.keyboard.up("ControlOrMeta");

    // Verify both flows are selected again
    await expect(firstCheckbox).toBeChecked();
    await expect(secondCheckbox).not.toBeChecked();
    await expect(thirdCheckbox).toBeChecked();

    const firstFlowName =
      (await page
        .locator("[data-testid='flow-name-div']")
        .first()
        .locator("span")
        .textContent()) ?? "";
    const secondFlowName =
      (await page
        .locator("[data-testid='flow-name-div']")
        .nth(1)
        .locator("span")
        .textContent()) ?? "";
    const thirdFlowName =
      (await page
        .locator("[data-testid='flow-name-div']")
        .nth(2)
        .locator("span")
        .textContent()) ?? "";

    // Test bulk delete
    await page.getByTestId("delete-bulk-btn").first().click();
    await page.getByText("This can't be undone.").isVisible({
      timeout: 1000,
    });
    await page.getByText("Delete").last().click();

    // Verify deletion success message
    await expect(page.getByText("Flows deleted successfully")).toBeVisible({
      timeout: 10000,
    });

    // Verify flows are deleted
    await expect(
      page.getByText(firstFlowName, { exact: true }),
    ).not.toBeVisible();
    await expect(page.getByText(secondFlowName, { exact: true })).toBeVisible();
    await expect(
      page.getByText(thirdFlowName, { exact: true }),
    ).not.toBeVisible();
  },
);
