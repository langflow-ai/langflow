import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { TEXTS } from "../../utils/constants/texts";
import { routeTestScopedDefaultFlowNames } from "../../utils/flow/route-test-scoped-default-flow-names";
import {
  getSidebarProjectButton,
  getSidebarProjectOptionsButton,
  getSidebarProjectRowById,
  getSidebarProjectRows,
} from "../../utils/project-sidebar";

// These tests intentionally mutate the shared project inventory, including one
// case that deletes every project. Keep those destructive transitions ordered.
test.describe.configure({ mode: "serial" });

const PROJECT_PATH_PREFIX = "/api/v1/projects/";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Deleting the last project leaves the home page re-rendering with a project
// id that has just become undefined. It used to reach the network as
// GET /api/v1/projects/undefined and come back 422, so watch every project
// request these destructive tests make and keep non-id ones out.
function collectInvalidProjectRequests(page: Page): string[] {
  const invalidRequests: string[] = [];
  page.on("request", (request) => {
    const { pathname } = new URL(request.url());
    if (!pathname.startsWith(PROJECT_PATH_PREFIX)) return;

    // Everything past the prefix identifies a single project; the list route
    // ends at the prefix and nested routes (download/, upload/) keep a slash.
    const projectId = pathname.slice(PROJECT_PATH_PREFIX.length);
    if (projectId === "" || projectId.includes("/")) return;
    if (UUID_PATTERN.test(projectId)) return;

    invalidRequests.push(`${request.method()} ${pathname}`);
  });
  return invalidRequests;
}

let invalidProjectRequests: string[] = [];

test.beforeEach(async ({ page }, testInfo) => {
  invalidProjectRequests = collectInvalidProjectRequests(page);
  await routeTestScopedDefaultFlowNames(page, testInfo, "folder-integrity");
});

test.afterEach(() => {
  expect(
    invalidProjectRequests,
    "the frontend requested a project by an id that is not a UUID",
  ).toEqual([]);
});

async function createAndRenameProject(page: Page, projectName: string) {
  const createResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "POST" &&
      url.pathname === "/api/v1/projects/"
    );
  });
  await page.getByTestId("add-project-button").click();
  const createResponse = await createResponsePromise;
  expect(
    createResponse.ok(),
    `Creating a project returned ${createResponse.status()}`,
  ).toBeTruthy();
  const createdProject = (await createResponse.json()) as { id?: unknown };
  expect(typeof createdProject.id).toBe("string");

  const projectId = createdProject.id as string;
  const projectRow = getSidebarProjectRowById(page, projectId);
  await expect(projectRow).toBeVisible();
  await projectRow.getByTestId(/^sidebar-nav-/).dblclick();

  const projectInput = projectRow.getByTestId("input-project");
  await expect(projectInput).toBeVisible();
  await projectInput.fill(projectName);
  const renameResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "PATCH" &&
      url.pathname === `/api/v1/projects/${projectId}`
    );
  });
  await page.keyboard.press("Enter");
  const renameResponse = await renameResponsePromise;
  expect(
    renameResponse.ok(),
    `Renaming project ${projectId} returned ${renameResponse.status()}`,
  ).toBeTruthy();
  expect(await renameResponse.finished()).toBeNull();
  await expect(projectRow.getByTestId(/^sidebar-nav-/)).toContainText(
    projectName,
  );
}

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
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Navigate to templates and create a flow first
    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    // Go back to folder view
    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="add-project-button"]', {
      timeout: 30000,
    });

    // Create a new folder and keep its server identity through the rename.
    await createAndRenameProject(page, "test-folder-to-delete");

    // Verify the folder exists in the sidebar
    const folderBeforeDelete = getSidebarProjectButton(
      page,
      "test-folder-to-delete",
    );
    await expect(folderBeforeDelete).toBeVisible({ timeout: 5000 });

    // Delete the folder
    await folderBeforeDelete.hover();
    await getSidebarProjectOptionsButton(page, "test-folder-to-delete").waitFor(
      { state: "visible", timeout: 5000 },
    );
    await getSidebarProjectOptionsButton(page, "test-folder-to-delete").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText(TEXTS.delete).last().click();

    // Verify success message
    await expect(page.getByText(TEXTS.toastProjectDeleted)).toBeVisible({
      timeout: 5000,
    });

    // Verify the folder is removed from the sidebar immediately (no stale data)
    await expect(folderBeforeDelete).not.toBeVisible({ timeout: 5000 });

    // Verify the page is still functional by checking for the add project button
    await expect(page.getByTestId("add-project-button")).toBeVisible({
      timeout: 5000,
    });
  },
);

test(
  "deleting one folder should not affect other folders",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Navigate to templates
    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    // Go back to folder view
    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="add-project-button"]', {
      timeout: 30000,
    });

    // Create first folder
    await createAndRenameProject(page, "folder-alpha");

    // Create second folder
    await createAndRenameProject(page, "folder-beta");

    // Verify both folders exist
    await expect(getSidebarProjectButton(page, "folder-alpha")).toBeVisible({
      timeout: 5000,
    });
    await expect(getSidebarProjectButton(page, "folder-beta")).toBeVisible({
      timeout: 5000,
    });

    // Delete the first folder
    const folderAlpha = getSidebarProjectButton(page, "folder-alpha");
    await folderAlpha.hover();
    await getSidebarProjectOptionsButton(page, "folder-alpha").waitFor({
      state: "visible",
      timeout: 5000,
    });
    await getSidebarProjectOptionsButton(page, "folder-alpha").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText(TEXTS.delete).last().click();

    // Verify success message
    await expect(page.getByText(TEXTS.toastProjectDeleted)).toBeVisible({
      timeout: 5000,
    });

    // Verify folder-alpha is removed
    await expect(folderAlpha).not.toBeVisible({
      timeout: 5000,
    });

    // Verify folder-beta still exists and is accessible
    const folderBeta = getSidebarProjectButton(page, "folder-beta");
    await expect(folderBeta).toBeVisible({ timeout: 5000 });

    // Click on folder-beta to ensure the app is functional
    await folderBeta.click();

    // The page should still be functional
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 10000,
    });

    // Clean up - delete the remaining folder
    await folderBeta.hover();
    await getSidebarProjectOptionsButton(page, "folder-beta").waitFor({
      state: "visible",
      timeout: 5000,
    });
    await getSidebarProjectOptionsButton(page, "folder-beta").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText(TEXTS.delete).last().click();

    await expect(page.getByText(TEXTS.toastProjectDeleted)).toBeVisible({
      timeout: 5000,
    });
  },
);

test(
  "creating a new folder after deletion should work correctly",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Navigate to templates
    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    // Go back to folder view
    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="add-project-button"]', {
      timeout: 30000,
    });

    // Create first folder
    await createAndRenameProject(page, "folder-one");

    // Delete the folder
    const folderOne = getSidebarProjectButton(page, "folder-one");
    await folderOne.hover();
    await getSidebarProjectOptionsButton(page, "folder-one").waitFor({
      state: "visible",
      timeout: 5000,
    });
    await getSidebarProjectOptionsButton(page, "folder-one").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText(TEXTS.delete).last().click();

    await expect(page.getByText(TEXTS.toastProjectDeleted)).toBeVisible({
      timeout: 5000,
    });

    // Verify folder is deleted
    await expect(folderOne).not.toBeVisible({
      timeout: 5000,
    });

    // Create a new folder immediately after deletion.
    await createAndRenameProject(page, "folder-two");

    const folderTwo = getSidebarProjectButton(page, "folder-two");
    await expect(folderTwo).toBeVisible({ timeout: 5000 });

    // Clean up
    await folderTwo.hover();
    await getSidebarProjectOptionsButton(page, "folder-two").waitFor({
      state: "visible",
      timeout: 5000,
    });
    await getSidebarProjectOptionsButton(page, "folder-two").click();
    await page.getByTestId("btn-delete-project").click();
    await page.getByText(TEXTS.delete).last().click();

    await expect(page.getByText(TEXTS.toastProjectDeleted)).toBeVisible({
      timeout: 5000,
    });
  },
);

test(
  "creating a flow after deleting all folders should create a default folder",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    // Get all folders in the sidebar and delete them one by one
    // Delete all folders until none are left
    let folderCount = await getSidebarProjectRows(page).count();

    while (folderCount > 0) {
      // Get the first folder
      const firstFolder = getSidebarProjectRows(page).first();

      // Hover and click more options
      await firstFolder.getByTestId(/^sidebar-nav-/).hover();

      const moreOptionsButton = firstFolder.getByTestId(
        /^more-options-button_/,
      );

      // Wait for the button to appear after hover
      await moreOptionsButton.waitFor({ state: "visible", timeout: 5000 });
      await moreOptionsButton.click();

      await page.getByTestId("btn-delete-project").click();
      await page.getByText(TEXTS.delete).last().click();

      // Wait for deletion to complete
      await expect(page.getByText(TEXTS.toastProjectDeleted)).toBeVisible({
        timeout: 5000,
      });

      // Wait a bit for UI to update
      await page.waitForTimeout(500);

      // Recount folders
      folderCount = await getSidebarProjectRows(page).count();
    }

    // Now create a new flow using the empty state button on main page
    // This should trigger creation of a default folder
    await page.waitForSelector('[data-testid="new_project_btn_empty_page"]', {
      timeout: 30000,
    });

    await page.getByTestId("new_project_btn_empty_page").click();

    // The empty-state CTA can either open the templates modal directly
    // (EmptyPageCommunity) or surface the FlowBuilderWelcome overlay
    // (EmptyFolder → useStartNewFlow). Race both and click "Browse more"
    // when the overlay shows up so we always end up on the templates modal.
    await Promise.race([
      page.waitForSelector('[data-testid="modal-title"]', { timeout: 30000 }),
      page.waitForSelector('[data-testid="flow-builder-welcome-panel"]', {
        timeout: 30000,
      }),
    ]);
    if (
      (await page
        .locator('[data-testid="flow-builder-welcome-panel"]')
        .count()) > 0
    ) {
      await page.getByTestId("flow-builder-welcome-browse-more").click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 30000,
      });
    }

    // Navigate to templates
    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    // Go back to folder view
    await page.getByTestId("icon-ChevronLeft").first().click();

    // Verify that a default folder ("Starter Project") was created
    await expect(getSidebarProjectButton(page, "Starter Project")).toBeVisible({
      timeout: 10000,
    });

    // Verify we can click on the folder and see the flow
    await getSidebarProjectButton(page, "Starter Project").click();

    // The folder should contain our newly created flow. Templates render an
    // extra example list-card alongside the user's flow when the folder is
    // freshly created, so scope to the first match to satisfy strict mode.
    await expect(page.getByTestId("list-card").first()).toBeVisible({
      timeout: 5000,
    });
  },
);
