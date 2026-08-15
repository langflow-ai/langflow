import type { Locator, Page } from "@playwright/test";

export const getSidebarProjectRows = (page: Page): Locator =>
  page.getByTestId("project-sidebar").locator("[data-project-id]");

export const getSidebarProjectRowById = (
  page: Page,
  projectId: string,
): Locator =>
  page
    .getByTestId("project-sidebar")
    .locator(`[data-project-id="${projectId}"]`);

export const getSidebarProjectRow = (
  page: Page,
  projectName: string,
): Locator =>
  getSidebarProjectRows(page).filter({
    has: page.getByText(projectName, { exact: true }),
  });

export const getSidebarProjectButton = (
  page: Page,
  projectName: string,
): Locator =>
  getSidebarProjectRow(page, projectName).getByTestId(/^sidebar-nav-/);

export const getSidebarProjectOptionsButton = (
  page: Page,
  projectName: string,
): Locator =>
  getSidebarProjectRow(page, projectName).getByTestId(/^more-options-button_/);
