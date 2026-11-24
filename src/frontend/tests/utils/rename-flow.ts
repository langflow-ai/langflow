import { expect, type Page } from "@playwright/test";
import { TIMEOUTS } from "./constants/timeouts";
import { waitForFlowEditorReady } from "./flow/wait-for-flow-editor-ready";

export const renameFlow = async (
  page: Page,
  {
    flowName,
    flowDescription,
  }: { flowName?: string; flowDescription?: string } = {},
) => {
  await waitForFlowEditorReady(page);

  const flowMenuButton = page.getByTestId("menu_bar_display");
  await expect(flowMenuButton).toBeVisible({ timeout: TIMEOUTS.standard });
  await expect(flowMenuButton).toBeEnabled();
  await flowMenuButton.click();

  const flowNameField = page.getByTestId("input-flow-name");
  await expect(flowNameField).toBeVisible({ timeout: TIMEOUTS.standard });
  await flowNameField.click();

  const flowNameInput = await flowNameField.inputValue();
  if (flowName) {
    await flowNameField.fill(flowName);
  }

  const flowDescriptionInput = await page
    .getByTestId("input-flow-description")
    .inputValue();

  if (flowDescription) {
    await page.getByTestId("input-flow-description").fill(flowDescription);
  }

  if (flowName || flowDescription) {
    const saveButton = page.getByTestId("save-flow-settings");
    await expect(saveButton).toBeEnabled();
    await saveButton.click();
    const savedToast = page.getByText("Changes saved successfully").last();
    await expect(savedToast).toBeVisible({ timeout: TIMEOUTS.standard });
    await savedToast.click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    if (flowName) {
      await expect(page.getByTestId("flow_name")).toHaveText(flowName, {
        timeout: TIMEOUTS.standard,
      });
    }
  } else {
    await expect(page.getByTestId("save-flow-settings")).toBeDisabled();
    const cancelButton = page.getByTestId("cancel-flow-settings");
    await expect(cancelButton).toBeEnabled();
    await cancelButton.click();
  }

  return {
    flowName: flowNameInput,
    flowDescription: flowDescriptionInput,
  };
};
