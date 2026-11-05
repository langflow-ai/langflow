import { expect, type LangflowPage } from "../fixtures";
import { TIMEOUTS } from "./constants/timeouts";

/** A full reload initializes the app again before fetching the trigger list. */
export async function navigateToTriggersSettings(page: LangflowPage) {
  await page.goto("/settings/triggers");
  await expect(
    page.getByRole("heading", { name: "Triggers", exact: true }),
  ).toBeVisible({ timeout: TIMEOUTS.standard });
  await expect(
    page
      .getByTestId("triggers-table-mine")
      .or(page.getByTestId("triggers-empty")),
  ).toBeVisible({ timeout: TIMEOUTS.standard });
}
