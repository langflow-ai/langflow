import { expect, type Page } from "@playwright/test";
import { TIMEOUTS } from "./constants/timeouts";

export const navigateSettingsPages = async (
  page: Page,
  pageName: string,
  settingsMenuName: string,
) => {
  if (!pageName) {
    return;
  }
  await page.getByTestId("user-profile-settings").click();
  const settingsButton = page.getByTestId("menu_settings_button");
  await expect(settingsButton).toBeVisible({ timeout: TIMEOUTS.medium });
  await settingsButton.click();
  await page.waitForURL(/\/settings(?:\/|$)/, { timeout: TIMEOUTS.standard });

  if (settingsMenuName) {
    const settingsMenuItem = page.getByTestId(
      `sidebar-nav-${settingsMenuName}`,
    );
    await expect(settingsMenuItem).toBeVisible({ timeout: TIMEOUTS.standard });
    await settingsMenuItem.click();
    await expect(page.getByTestId("settings_menu_header")).toBeVisible({
      timeout: TIMEOUTS.standard,
    });
  }
};
