import { expect, type Page } from "@playwright/test";
import { waitForFlowEditorReady } from "./flow/wait-for-flow-editor-ready";

export const addLegacyComponents = async (page: Page) => {
  const optionsTrigger = page.getByTestId("sidebar-options-trigger");
  await expect(optionsTrigger).toBeVisible();
  await expect(optionsTrigger).toBeEnabled();

  if ((await optionsTrigger.getAttribute("aria-expanded")) !== "true") {
    await optionsTrigger.click();
  }
  await expect(optionsTrigger).toHaveAttribute("aria-expanded", "true");

  const legacySwitch = page.getByTestId("sidebar-legacy-switch");
  await expect(legacySwitch).toBeVisible();
  await expect(legacySwitch).toBeEnabled();

  if ((await legacySwitch.getAttribute("data-state")) !== "checked") {
    await legacySwitch.click();
  }
  await expect(legacySwitch).toHaveAttribute("data-state", "checked");
  await expect(legacySwitch).toHaveAttribute("aria-checked", "true");

  await optionsTrigger.click();
  await expect(optionsTrigger).toHaveAttribute("aria-expanded", "false");
  await waitForFlowEditorReady(page);
};
