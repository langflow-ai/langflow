import type { Page } from "@playwright/test";

// Single source of truth for the "new project" button selector. Some tests
// historically referenced it via id ([id="new-project-btn"]), others via
// data-testid; centralizing here keeps both call sites in sync if the
// attribute ever changes.
const NEW_PROJECT_BUTTON_SELECTOR = '[id="new-project-btn"]';

/**
 * Waits for the "new project" button on the projects/home page to be ready.
 * Use when a test only needs to confirm the main page has finished loading
 * before reading or interacting with surrounding UI (it does NOT click).
 */
export const waitForNewProjectButton = async (
  page: Page,
  options?: { timeout?: number },
) => {
  await page.waitForSelector(NEW_PROJECT_BUTTON_SELECTOR, {
    timeout: options?.timeout ?? 30000,
  });
};

/**
 * Opens the templates modal from the projects page. Encapsulates the post-
 * 1.10 screen flow so future intermediate-screen changes only need to be
 * applied here:
 *   1. wait for the "new project" button,
 *   2. click it,
 *   3. dismiss the intermediate "What do you want to build?" welcome panel
 *      by clicking its "Browse more…" card,
 *   4. wait for the templates modal title to render.
 *
 * Replaces the legacy `page.getByTestId("new-project-btn").click()` pattern
 * that assumed the modal opened directly.
 */
export const openTemplatesModal = async (
  page: Page,
  options?: { buttonTimeout?: number; modalTimeout?: number },
) => {
  await waitForNewProjectButton(page, { timeout: options?.buttonTimeout });
  await page.getByTestId("new-project-btn").click();

  await page.waitForSelector('[data-testid="flow-builder-welcome-panel"]', {
    timeout: 5000,
  });
  await page.getByTestId("flow-builder-welcome-browse-more").click();

  await page.waitForSelector('[data-testid="modal-title"]', {
    timeout: options?.modalTimeout ?? 5000,
  });
};
