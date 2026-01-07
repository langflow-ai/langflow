import type { Page } from "@playwright/test";
import { adjustScreenView } from "./adjust-screen-view";
import { selectGptModel } from "./select-gpt-model";
import { updateOldComponents } from "./update-old-components";

export async function initialGPTsetup(
  page: Page,
  options?: {
    skipAdjustScreenView?: boolean;
    skipUpdateOldComponents?: boolean;
    skipSelectGptModel?: boolean;
  },
) {
  if (!options?.skipAdjustScreenView) {
    await adjustScreenView(page);
  }
  if (!options?.skipUpdateOldComponents) {
    await updateOldComponents(page);
  }
  if (!options?.skipSelectGptModel) {
    await selectGptModel(page);
  }
}
