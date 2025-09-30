import { expect, type Page } from "playwright/test";

export const navigateSettingsPages = async (
  page: Page,
  pageName: string,
  settingsMenuName: string,
) => {
  if (!pageName) {
    return;
  }
  await page.getByTestId("user-profile-settings").click();
  await page.getByText(`${pageName}`).first().click();

  if (settingsMenuName) {
    await page.getByText(`${settingsMenuName}`).first().click();
    await page.waitForSelector('[data-testid="settings_menu_header"]', {
      timeout: 5000,
    });
    await page.waitForTimeout(500);
    await expect(page.getByTestId("settings_menu_header").last()).toContainText(
      settingsMenuName,
    );
  }
};
