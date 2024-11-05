import { expect, test } from "@playwright/test";

test("user must be able to minimize and expand a component", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("blank-flow").click();

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("text input");
  await page.waitForTimeout(1000);

  await page
    .getByTestId("inputsText Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTestId("zoom_out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  await page.getByTestId("more-options-modal").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("minimize-button-modal").first().click();

  await page.waitForTimeout(1000);

  await expect(
    page.locator(".react-flow__handle-left.no-show").first(),
  ).toBeVisible();

  await expect(
    page.locator(".react-flow__handle-right.no-show").first(),
  ).toBeVisible();

  await page.getByTestId("more-options-modal").click();

  await page.waitForTimeout(1000);
  await page.getByTestId("expand-button-modal").first().click();

  await page.waitForTimeout(1000);

  await expect(page.locator(".react-flow__handle-left").first()).toBeVisible();

  await expect(page.locator(".react-flow__handle-right").first()).toBeVisible();
});
