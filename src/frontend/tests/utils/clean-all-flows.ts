import { Page } from "playwright/test";

export const cleanAllFlows = async (page: Page) => {
  const emptyPageDescription = page.getByTestId("empty_page_description");
  const dropdownMenu = page.getByTestId("home-dropdown-menu");

  // Delete every flow until the global empty state renders. Each iteration
  // first waits for the projects list to settle into a KNOWN terminal state —
  // the empty marker OR at least one flow card — before acting.
  //
  // Why: on a slow runner the list can still be mounting when the loop runs.
  // The previous version blindly clicked `home-dropdown-menu`; with no card
  // present yet that click hung for the full 20s action timeout (the observed
  // CI deadlock). Waiting for a terminal state first removes the race; the
  // iteration cap makes a genuinely stuck view fail fast with a clear
  // downstream assertion instead of looping forever.
  const MAX_DELETIONS = 50;
  for (let i = 0; i < MAX_DELETIONS; i++) {
    if ((await emptyPageDescription.count()) > 0) return;

    try {
      await Promise.any([
        emptyPageDescription.waitFor({ state: "visible", timeout: 15000 }),
        dropdownMenu.first().waitFor({ state: "visible", timeout: 15000 }),
      ]);
    } catch {
      // Neither the empty marker nor a flow card appeared — the page is in an
      // unexpected view (not the projects home). Stop here and let the
      // caller's own assertions surface the real problem.
      return;
    }

    // The settle wait may have resolved because the empty state arrived.
    if ((await emptyPageDescription.count()) > 0) return;

    await dropdownMenu.first().click();
    await page.getByTestId("btn_delete_dropdown_menu").first().click();
    await page
      .getByTestId("btn_delete_delete_confirmation_modal")
      .first()
      .click();
    await page.waitForTimeout(1000);
  }
};
