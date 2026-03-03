import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

/**
 * Tests for folder deletion integrity
 *
 * These tests verify that:
 * 1. After deleting a folder, the UI properly updates (no stale data)
 * 2. Deleting a folder when another exists keeps the app functional
 * 3. Creating folders after deletion works correctly
 */

test(
  "deleting a folder should update the folder list immediately",
  { tag: ["@release", "@api", "@folder"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Navigate to templates and create a flow first
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    // Go back to folder view
    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="add-project-button"]', {
      timeout: 30000,
    });

    // Create a new folder
    await page.getByTestId("add-project-button").click();

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .waitFor({ state: "visible", timeout: 10000 });

    // Rename the folder for easier identification
    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .dblclick();

    const folderInput = page.getByTestId("input-project");
    await folderInput.fill("test-folder-to-delete");
    await page.keyboard.press("Enter");

    // Wait for the folder to be renamed
    await page.getByText("test-folder-to-delete").last().waitFor({
      state: "visible",
      timeout: 10000,
    });

    // Verify the folder exists in the sidebar
    const folderBeforeDelete = page.getByTestId(
      "sidebar-nav-test-folder-to-delete",
    );
    await expect(folderBeforeDelete).toBeVisible({ timeout: 5000 });

    // Delete the folder
    await folderBeforeDelete.hover();
    await page.getByTestId("more-options-button_test-folder-to-delete").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText("Delete").last().click();

    // Verify success message
    await expect(page.getByText("Project deleted successfully")).toBeVisible({
      timeout: 5000,
    });

    // Verify the folder is removed from the sidebar immediately (no stale data)
    await expect(
      page.getByTestId("sidebar-nav-test-folder-to-delete"),
    ).not.toBeVisible({ timeout: 5000 });

    // Verify the page is still functional by checking for the add project button
    await expect(page.getByTestId("add-project-button")).toBeVisible({
      timeout: 5000,
    });
  },
);

test(
  "deleting one folder should not affect other folders",
  { tag: ["@release", "@api", "@folder"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Navigate to templates
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    // Go back to folder view
    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="add-project-button"]', {
      timeout: 30000,
    });

    // Create first folder
    await page.getByTestId("add-project-button").click();

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .waitFor({ state: "visible", timeout: 10000 });

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .dblclick();

    await page.getByTestId("input-project").fill("folder-alpha");
    await page.keyboard.press("Enter");

    await page.getByText("folder-alpha").last().waitFor({
      state: "visible",
      timeout: 10000,
    });

    // Create second folder
    await page.getByTestId("add-project-button").click();

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .waitFor({ state: "visible", timeout: 10000 });

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .dblclick();

    await page.getByTestId("input-project").fill("folder-beta");
    await page.keyboard.press("Enter");

    await page.getByText("folder-beta").last().waitFor({
      state: "visible",
      timeout: 10000,
    });

    // Verify both folders exist
    await expect(page.getByTestId("sidebar-nav-folder-alpha")).toBeVisible({
      timeout: 5000,
    });
    await expect(page.getByTestId("sidebar-nav-folder-beta")).toBeVisible({
      timeout: 5000,
    });

    // Delete the first folder
    const folderAlpha = page.getByTestId("sidebar-nav-folder-alpha");
    await folderAlpha.hover();
    await page.getByTestId("more-options-button_folder-alpha").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText("Delete").last().click();

    // Verify success message
    await expect(page.getByText("Project deleted successfully")).toBeVisible({
      timeout: 5000,
    });

    // Verify folder-alpha is removed
    await expect(page.getByTestId("sidebar-nav-folder-alpha")).not.toBeVisible({
      timeout: 5000,
    });

    // Verify folder-beta still exists and is accessible
    const folderBeta = page.getByTestId("sidebar-nav-folder-beta");
    await expect(folderBeta).toBeVisible({ timeout: 5000 });

    // Click on folder-beta to ensure the app is functional
    await folderBeta.click();

    // The page should still be functional
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 10000,
    });

    // Clean up - delete the remaining folder
    await folderBeta.hover();
    await page.getByTestId("more-options-button_folder-beta").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText("Delete").last().click();

    await expect(page.getByText("Project deleted successfully")).toBeVisible({
      timeout: 5000,
    });
  },
);

test(
  "creating a new folder after deletion should work correctly",
  { tag: ["@release", "@api", "@folder"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Navigate to templates
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    // Go back to folder view
    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="add-project-button"]', {
      timeout: 30000,
    });

    // Create first folder
    await page.getByTestId("add-project-button").click();

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .waitFor({ state: "visible", timeout: 10000 });

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .dblclick();

    await page.getByTestId("input-project").fill("folder-one");
    await page.keyboard.press("Enter");

    await page.getByText("folder-one").last().waitFor({
      state: "visible",
      timeout: 10000,
    });

    // Delete the folder
    const folderOne = page.getByTestId("sidebar-nav-folder-one");
    await folderOne.hover();
    await page.getByTestId("more-options-button_folder-one").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText("Delete").last().click();

    await expect(page.getByText("Project deleted successfully")).toBeVisible({
      timeout: 5000,
    });

    // Verify folder is deleted
    await expect(page.getByTestId("sidebar-nav-folder-one")).not.toBeVisible({
      timeout: 5000,
    });

    // Create a new folder immediately after deletion
    await page.getByTestId("add-project-button").click();

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .waitFor({ state: "visible", timeout: 10000 });

    await page
      .locator("[data-testid='project-sidebar']")
      .getByText("New Project")
      .last()
      .dblclick();

    await page.getByTestId("input-project").fill("folder-two");
    await page.keyboard.press("Enter");

    // The new folder should be created successfully without any stale data issues
    await page.getByText("folder-two").last().waitFor({
      state: "visible",
      timeout: 10000,
    });

    const folderTwo = page.getByTestId("sidebar-nav-folder-two");
    await expect(folderTwo).toBeVisible({ timeout: 5000 });

    // Clean up
    await folderTwo.hover();
    await page.getByTestId("more-options-button_folder-two").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText("Delete").last().click();

    await expect(page.getByText("Project deleted successfully")).toBeVisible({
      timeout: 5000,
    });
  },
);

test(
  "creating a flow after deleting all folders should create a default folder",
  { tag: ["@release", "@api", "@folder"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    // Get all folders in the sidebar and delete them one by one
    const projectSidebar = page.locator("[data-testid='project-sidebar']");

    // Delete all folders until none are left
    let folderCount = await projectSidebar
      .locator('[data-testid^="sidebar-nav-"]')
      .filter({ hasNotText: "add_note" })
      .count();

    while (folderCount > 0) {
      // Get the first folder
      const firstFolder = projectSidebar
        .locator('[data-testid^="sidebar-nav-"]')
        .filter({ hasNotText: "add_note" })
        .first();
      const folderTestId = await firstFolder.getAttribute("data-testid");

      if (!folderTestId) {
        break;
      }

      // Extract folder name from testid (e.g., "sidebar-nav-Starter Project" -> "starter-project")
      const folderName = folderTestId.replace("sidebar-nav-", "");
      const kebabName = folderName.toLowerCase().replace(/\s+/g, "-");

      // Hover and click more options
      await firstFolder.hover();

      // Try to find and click the more options button
      const moreOptionsButton = page.getByTestId(
        `more-options-button_${kebabName}`,
      );

      if (await moreOptionsButton.isVisible()) {
        await moreOptionsButton.click();
      } else {
        // Try with the original name format
        const altMoreOptions = page
          .locator(`[data-testid^="more-options-button_"]`)
          .first();
        await altMoreOptions.click();
      }

      await page.getByTestId("btn-delete-project").click();
      await page.getByText("Delete").last().click();

      // Wait for deletion to complete
      await expect(page.getByText("Project deleted successfully")).toBeVisible({
        timeout: 5000,
      });

      // Wait a bit for UI to update
      await page.waitForTimeout(500);

      // Recount folders
      folderCount = await projectSidebar
        .locator('[data-testid^="sidebar-nav-"]')
        .filter({ hasNotText: "add_note" })
        .count();
    }

    // Now create a new flow using the empty state button on main page
    // This should trigger creation of a default folder
    await page.waitForSelector('[data-testid="new_project_btn_empty_page"]', {
      timeout: 30000,
    });

    await page.getByTestId("new_project_btn_empty_page").click();

    // Navigate to templates
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    // Go back to folder view
    await page.getByTestId("icon-ChevronLeft").first().click();

    // Verify that a default folder ("Starter Project") was created
    await expect(page.getByTestId("sidebar-nav-Starter Project")).toBeVisible({
      timeout: 10000,
    });

    // Verify we can click on the folder and see the flow
    await page.getByTestId("sidebar-nav-Starter Project").click();

    // The folder should contain our newly created flow
    await expect(page.getByTestId("list-card")).toBeVisible({
      timeout: 5000,
    });
  },
);
