import { expect, type Page } from "@playwright/test";

export const cleanAllFlows = async (page: Page) => {
  const emptyPageDescription = page.getByTestId("empty_page_description");
  const dropdownMenu = page.getByTestId("home-dropdown-menu");

  const MAX_DELETIONS = 50;
  for (let i = 0; i < MAX_DELETIONS; i++) {
    if (await emptyPageDescription.isVisible().catch(() => false)) return;

    await Promise.any([
      emptyPageDescription.waitFor({ state: "visible", timeout: 15000 }),
      dropdownMenu.first().waitFor({ state: "visible", timeout: 15000 }),
    ]);

    if (await emptyPageDescription.isVisible().catch(() => false)) return;

    const cardCountBeforeDelete = await dropdownMenu.count();
    await dropdownMenu.first().click();
    await page.getByTestId("btn_delete_dropdown_menu").first().click();
    const [deleteResponse] = await Promise.all([
      page.waitForResponse(
        (response) =>
          response.request().method() === "DELETE" &&
          new URL(response.url()).pathname === "/api/v1/flows/",
      ),
      page.getByTestId("btn_delete_delete_confirmation_modal").first().click(),
    ]);
    expect(deleteResponse.ok()).toBe(true);
    await expect(dropdownMenu).toHaveCount(cardCountBeforeDelete - 1);
  }

  // The final iteration can delete the last flow and fall out of the loop
  // normally, so confirm the empty state before reporting a failure.
  if (await emptyPageDescription.isVisible().catch(() => false)) return;

  throw new Error(`Unable to delete all flows after ${MAX_DELETIONS} attempts`);
};
