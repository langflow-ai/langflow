import type { Page } from "@playwright/test";

export const renameFlow = async (
  page: Page,
  {
    flowName,
    flowDescription,
  }: { flowName?: string; flowDescription?: string } = {},
) => {
  await page.getByTestId("flow_name").isVisible({ timeout: 3000 });
  await page.getByTestId("flow_name").hover({ timeout: 3000 });
  await page.getByTestId("flow_name").click({ timeout: 3000 });

  // Wait for the input to be stable and visible
  await page.waitForTimeout(1500);

  // Wait for the input field to be attached and stable
  await page.waitForSelector('[data-testid="input-flow-name"]', {
    state: "attached",
    timeout: 10000,
  });

  await page.waitForTimeout(1000);

  // Use a more robust approach to click the input with retry logic
  const inputLocator = page.getByTestId("input-flow-name");
  await inputLocator.waitFor({ state: "visible", timeout: 10000 });

  // Retry clicking if element gets detached
  let clicked = false;
  for (let i = 0; i < 3; i++) {
    try {
      await inputLocator.click({ timeout: 10000, force: true });
      clicked = true;
      break;
    } catch (error) {
      if (i === 2) throw error;
      await page.waitForTimeout(1000);
    }
  }

  const flowNameInput = await inputLocator.inputValue();
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

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
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
