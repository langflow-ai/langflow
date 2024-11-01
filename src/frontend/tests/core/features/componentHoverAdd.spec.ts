import { expect, test } from "@playwright/test";

test("user can add components by hovering and clicking the plus icon", async ({
  page,
}) => {
  // Navigate to homepage and handle initial modal
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
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

  // Start with blank flow
  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(1000);

  // Search for a component
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("chat input");
  await page.waitForTimeout(500);

  // Hover over the component and verify plus icon
  const componentLocator = page.getByTestId("inputsChat Input");
  // Find the plus icon within the specific component container
  const plusIcon = componentLocator.getByTestId("icon-Plus");

  // Get the opacity
  const opacity = await plusIcon.evaluate((el) =>
    window.getComputedStyle(el).getPropertyValue("opacity"),
  );

  await expect(plusIcon).toBeVisible();

  await expect(opacity).toBe("0");

  // Hover over the component
  await componentLocator.hover();

  // Check if the plus icon is visible and has full opacity

  await expect(plusIcon).toBeVisible();

  await page.waitForTimeout(500);

  const opacityAfterHover = await plusIcon.evaluate((el) =>
    window.getComputedStyle(el).getPropertyValue("opacity"),
  );

  await expect(opacityAfterHover).toBe("1");

  // Click the plus icon associated with this component
  await plusIcon.click();
  await page.waitForTimeout(500);

  // Verify component was added to the flow
  const addedComponent = await page.locator(".react-flow__node").first();
  await expect(addedComponent).toBeVisible();
});
