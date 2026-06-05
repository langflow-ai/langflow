import type { Page } from "@playwright/test";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

// Single source of truth for the "new project" button selector. Some tests
// historically referenced it via id ([id="new-project-btn"]), others via
// data-testid; centralizing here keeps both call sites in sync if the
// attribute ever changes.
const NEW_PROJECT_BUTTON_SELECTOR = `[id="${TID.newProjectBtn}"]`;

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
    timeout: options?.timeout ?? TIMEOUTS.standard,
  });
};

/**
 * Opens the templates modal from the projects page. Encapsulates the post-
 * 1.10 screen flow so future intermediate-screen changes only need to be
 * applied here:
 *   1. wait for the "new project" button,
 *   2. click it — both the header "New Flow" button and the empty-page CTA
 *      now navigate to a fresh flow with the welcome overlay,
 *   3. if the welcome overlay surfaces, click "Browse more templates" to
 *      open the templates modal,
 *   4. wait for the templates modal title to render.
 *
 * Pass `fromEmptyPage: true` when the home page is in its empty state, where
 * the CTA carries the `new_project_btn_empty_page` test id instead of the
 * header `new-project-btn`.
 *
 * Replaces the legacy `page.getByTestId("new-project-btn").click()` pattern
 * that assumed the modal opened directly.
 */
export const openTemplatesModal = async (
  page: Page,
  options?: {
    buttonTimeout?: number;
    modalTimeout?: number;
    fromEmptyPage?: boolean;
  },
) => {
  await waitForNewProjectButton(page, { timeout: options?.buttonTimeout });
  await page
    .getByTestId(
      options?.fromEmptyPage ? TID.newProjectBtnEmptyPage : TID.newProjectBtn,
    )
    .click();

  // After clicking the header "New Flow" button the app navigates to a
  // freshly-created empty flow and surfaces the FlowBuilderWelcome overlay.
  // On a slow runner the navigation + canvas mount can take well over 5s,
  // so race the welcome overlay against the templates modal — whichever
  // shows up first wins, and we only click "Browse more" when the overlay
  // actually surfaces.
  const welcomeSelector = '[data-testid="flow-builder-welcome-panel"]';
  const modalSelector = `[data-testid="${TID.modalTitle}"]`;

  await Promise.race([
    page.waitForSelector(welcomeSelector, { timeout: TIMEOUTS.standard }),
    page.waitForSelector(modalSelector, { timeout: TIMEOUTS.standard }),
  ]);

  if ((await page.locator(welcomeSelector).count()) > 0) {
    await page.getByTestId("flow-builder-welcome-browse-more").click();
  }

  await page.waitForSelector(modalSelector, {
    timeout: options?.modalTimeout ?? TIMEOUTS.standard,
  });
};
