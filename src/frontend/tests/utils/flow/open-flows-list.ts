import { expect, type Locator, type Page } from "@playwright/test";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

export async function openFlowsList(page: Page): Promise<Locator> {
  await page.goto("/flows");

  const mainpageTitle = page.getByTestId(TID.mainpageTitle);
  await expect(mainpageTitle).toBeVisible({
    timeout: TIMEOUTS.standard,
  });

  const cardsWrapper = page.getByTestId("cards-wrapper");
  const hasCardsWrapper = await cardsWrapper
    .waitFor({ state: "visible", timeout: TIMEOUTS.short })
    .then(() => true)
    .catch(() => false);

  return hasCardsWrapper ? cardsWrapper : mainpageTitle;
}
