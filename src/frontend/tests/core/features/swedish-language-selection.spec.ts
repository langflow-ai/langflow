import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

const SWEDISH_DESCRIPTION = "Välj visningsspråk för Langflows gränssnitt.";

test(
  "selects Swedish and keeps it after reload",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, {
      skipModal: true,
      seedFlowIfEmpty: false,
    });
    await page.goto("/settings/general");

    await expect(page.getByRole("heading", { name: "Language" })).toBeVisible();

    const languageSelect = page.locator('select[aria-label="Select language"]');
    await expect(languageSelect).toHaveValue("en");
    await languageSelect.selectOption("sv");

    await expect(page.locator("html")).toHaveAttribute("lang", "sv");
    await expect(page.getByText(SWEDISH_DESCRIPTION)).toBeVisible();

    await page.reload();

    await expect(page.locator("html")).toHaveAttribute("lang", "sv");
    await expect(page.getByText(SWEDISH_DESCRIPTION)).toBeVisible();
  },
);
