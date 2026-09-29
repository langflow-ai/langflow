import type { Page } from "@playwright/test";

/**
 * Answer every contested component in the review dialog.
 *
 * Updating the original flow is refused while any conflict is unanswered, so a
 * test that wants to reach that exit has to make the same choices a person
 * would. Cards open closed and fold back once answered, which is why each one
 * is opened before its radio is clicked.
 */
export async function resolveConflicts(
  page: Page,
  side: "mine" | "theirs" = "mine",
): Promise<number> {
  const cards = page.locator('[data-testid^="conflict-resolve-"]');
  const total = await cards.count();
  for (let index = 0; index < total; index++) {
    const card = cards.nth(index);
    await card.locator('[data-testid^="conflict-toggle-"]').click();
    await card
      .getByRole("radio")
      .nth(side === "mine" ? 0 : 1)
      .click();
  }
  return total;
}
