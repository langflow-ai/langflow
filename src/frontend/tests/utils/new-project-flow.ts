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
 *   2. click it (header button navigates to a fresh flow with welcome
 *      overlay; empty-page button opens the templates modal directly),
 *   3. if the welcome overlay surfaces, click "Browse more templates" to
 *      open the templates modal,
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

  // After clicking the header "New Flow" button the app navigates to a
  // freshly-created empty flow and surfaces the FlowBuilderWelcome overlay.
  // On a slow runner the navigation + canvas mount can take well over 5s,
  // so race the welcome overlay against the templates modal — whichever
  // shows up first wins, and we only click "Browse more" when the overlay
  // actually surfaces.
  const welcomeSelector = '[data-testid="flow-builder-welcome-panel"]';
  const modalSelector = '[data-testid="modal-title"]';

  await Promise.race([
    page.waitForSelector(welcomeSelector, { timeout: 30000 }),
    page.waitForSelector(modalSelector, { timeout: 30000 }),
  ]);

  if ((await page.locator(welcomeSelector).count()) > 0) {
    await page.getByTestId("flow-builder-welcome-browse-more").click();
  }

  await page.waitForSelector(modalSelector, {
    timeout: options?.modalTimeout ?? 30000,
  });
};
