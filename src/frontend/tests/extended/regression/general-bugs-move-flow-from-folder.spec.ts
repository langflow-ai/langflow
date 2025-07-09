import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { renameFlow } from "../../utils/rename-flow";

test("user must be able to move flow from folder", async ({ page }) => {
  const randomName = Math.random().toString(36).substring(2, 15);

  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await renameFlow(page, { flowName: randomName });

  await page.getByTestId("icon-ChevronLeft").click();
  await page.waitForSelector('[data-testid="add-project-button"]', {
    timeout: 3000,
  });

  await page.getByTestId("add-project-button").click();

  //wait for the project to be created and changed to the new project
  await page.waitForTimeout(1000);

  await page.getByTestId("sidebar-nav-Starter Project").click();

  await page.getByText(randomName).hover();

  await page
    .getByTestId("list-card")
    .first()
    .dragTo(page.locator('//*[@id="sidebar-nav-New Project"]'));

  //wait for the drag and drop to be completed
  await page.waitForTimeout(1000);

  await page.getByTestId("sidebar-nav-New Project").click();

  await page.waitForSelector('[data-testid="list-card"]', {
    timeout: 3000,
  });

  const flowNameCount = await page.getByText(randomName).count();
  expect(flowNameCount).toBeGreaterThan(0);
});
