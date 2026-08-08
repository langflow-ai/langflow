import { type Page } from "@playwright/test";

export async function openFlowCard(
  page: Page,
  flowName: string,
): Promise<void> {
  const flowCard = page
    .getByTestId("list-card")
    .filter({ hasText: flowName })
    .first();

  await flowCard.waitFor({ state: "visible" });
  await flowCard.getByTestId("list-card-open-button").click();
}
