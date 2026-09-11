import type { Page, Response } from "@playwright/test";

/**
 * Resolves when the flow is actually written back to the server.
 *
 * Autosave is debounced by AUTOSAVE_DEBOUNCE_TIME, which is deliberately long
 * so that two people editing one flow spend less time diverging. Any fixed
 * sleep shorter than that window leaves the edit unsaved, and an assertion made
 * after it reads stale state — so wait for the write itself rather than for a
 * duration that has to be guessed.
 *
 * Call this *before* the interaction that triggers the save, and await the
 * returned promise after it.
 */
export function waitForFlowSave(
  page: Page,
  timeout = 20000,
): Promise<Response> {
  return page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes("/api/v1/flows/") &&
      response.ok(),
    { timeout },
  );
}
