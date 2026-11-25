import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { navigateSettingsPages } from "../../utils/go-to-settings";

const SWEDISH_DESCRIPTION = "Välj visningsspråk för Langflows gränssnitt.";

test("selects Swedish and keeps it after reload", {
  tag: ["@release", "@workspace"],
}, async ({ page }) => {
  await awaitBootstrapTest(page, {
    skipModal: true,
    seedFlowIfEmpty: false,
  });
  await navigateSettingsPages(page, "Settings", "General");

  await expect(
    page.getByText("Choose the display language for the Langflow interface."),
  ).toBeVisible();

  const languageSelect = page.getByRole("combobox", {
    name: "Select language",
  });
  await expect(languageSelect).toHaveText(/English/);
  await languageSelect.click();
  await page.getByRole("option", { name: "Svenska", exact: true }).click();

  await expect(page.locator("html")).toHaveAttribute("lang", "sv");
  await expect(page.getByText(SWEDISH_DESCRIPTION)).toBeVisible();

  await page.reload();

  await expect(page.locator("html")).toHaveAttribute("lang", "sv");
  await expect(page.getByText(SWEDISH_DESCRIPTION)).toBeVisible();
});
