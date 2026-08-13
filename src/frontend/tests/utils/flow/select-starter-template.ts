import { expect, type Page } from "@playwright/test";
import { TID } from "../constants/testIds";
import { TIMEOUTS } from "../constants/timeouts";

export async function selectStarterTemplate(
  page: Page,
  templateName: string,
): Promise<void> {
  await page.getByTestId(TID.sideNavAllTemplates).click();
  const template = page
    .getByRole("dialog")
    .getByTestId(`template-${templateName.replace(/ /g, "-").toLowerCase()}`);
  await expect(template).toBeVisible({ timeout: TIMEOUTS.standard });
  const [createResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === "/api/v1/flows/",
    ),
    template.click(),
  ]);
  expect(createResponse.ok()).toBe(true);
  await page.waitForURL(/\/flow\/[^/?#]+(?:\/folder\/[^/?#]+)?(?:[?#].*)?$/, {
    timeout: TIMEOUTS.standard,
  });
}
