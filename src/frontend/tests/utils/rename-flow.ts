import type { Page } from "playwright/test";

export const renameFlow = async (
  page: Page,
  {
    flowName,
    flowDescription,
  }: { flowName?: string; flowDescription?: string } = {},
) => {
  await page.getByTestId("flow_name").isVisible({ timeout: 3000 });
  await page.getByTestId("flow_name").click({ timeout: 3000 });
  await page.waitForTimeout(500);
  await page.getByTestId("input-flow-name").click({ timeout: 3000 });

  const flowNameInput = await page.getByTestId("input-flow-name").inputValue();
  if (flowName) {
    await page.getByTestId("input-flow-name").fill(flowName);
  }

  const flowDescriptionInput = await page
    .getByTestId("input-flow-description")
    .inputValue();

  if (flowDescription) {
    await page.getByTestId("input-flow-description").fill(flowDescription);
  }

  if (flowName || flowDescription) {
    await page.getByTestId("save-flow-settings").isEnabled({ timeout: 3000 });
    await page.getByTestId("save-flow-settings").click();
    await page
      .getByText("Changes saved successfully")
      .last()
      .isVisible({ timeout: 3000 });
    await page.getByText("Changes saved successfully").last().click();

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 30000,
    });
  } else {
    await page.getByTestId("save-flow-settings").isDisabled({ timeout: 3000 });
    await page.getByTestId("cancel-flow-settings").isEnabled({ timeout: 3000 });
    await page.getByTestId("cancel-flow-settings").click();
  }

  return {
    flowName: flowNameInput,
    flowDescription: flowDescriptionInput,
  };
};
