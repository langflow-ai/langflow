import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { renameFlow } from "../../utils/rename-flow";

test("user must be able to move flow from folder", async ({ page }) => {
  const randomName = Math.random().toString(36).substring(2, 15);

  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForTimeout(1000);

  await renameFlow(page, { flowName: randomName });

  await page.waitForTimeout(1000);

  await page.getByTestId("icon-ChevronLeft").click();
  await page.waitForSelector('[data-testid="add-project-button"]', {
    timeout: 10000,
  });

  // Only create a new folder if none exists besides "Starter Project"
  const newProjectExists =
    (await page.locator('[id="sidebar-nav-New Project"]').count()) > 0;

  if (!newProjectExists) {
    await page.getByTestId("add-project-button").click();
    await page.waitForTimeout(1000);
  }

  await page.getByTestId("sidebar-nav-Starter Project").click();
  await page.waitForTimeout(500);

  await page.getByText(randomName).waitFor({ timeout: 5000 });

  const targetFolder = page.locator('[id="sidebar-nav-New Project"]');
  await targetFolder.scrollIntoViewIfNeeded();

  await page
    .getByTestId("list-card")
    .filter({ hasText: randomName })
    .dragTo(targetFolder);

  await page.waitForTimeout(1000);

  await page.getByTestId("sidebar-nav-New Project").click();

  await expect(page.getByText(randomName)).toBeVisible({ timeout: 10000 });
});
