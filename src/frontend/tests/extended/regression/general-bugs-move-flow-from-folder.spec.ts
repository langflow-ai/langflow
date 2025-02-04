import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test("user must be able to move flow from folder", async ({ page }) => {
  const randomName = Math.random().toString(36).substring(2, 15);

  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="input-flow-name"]', {
    timeout: 3000,
  });

  await page.getByTestId("flow_menu_trigger").click();
  await page.getByText("Edit Details").first().click();
  await page.getByPlaceholder("Flow name").fill(randomName);

  await page.getByTestId("save-flow-settings").click();

  await page.getByText("Changes saved successfully").isVisible();

  await page.getByTestId("icon-ChevronLeft").click();
  await page.waitForSelector('[data-testid="add-folder-button"]', {
    timeout: 3000,
  });

  await page.getByTestId("add-folder-button").click();

  //wait for the folder to be created and changed to the new folder
  await page.waitForTimeout(1000);

  await page.getByTestId("sidebar-nav-My Projects").click();

  await page.getByText(randomName).hover();

  await page
    .getByTestId("list-card")
    .first()
    .dragTo(page.locator('//*[@id="sidebar-nav-New Folder"]'));

  //wait for the drag and drop to be completed
  await page.waitForTimeout(1000);

  await page.getByTestId("sidebar-nav-New Folder").click();

  await page.waitForSelector('[data-testid="list-card"]', {
    timeout: 3000,
  });

  const flowNameCount = await page.getByText(randomName).count();
  expect(flowNameCount).toBeGreaterThan(0);
});
