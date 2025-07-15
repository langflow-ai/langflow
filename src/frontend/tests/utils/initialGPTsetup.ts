import type { Page } from "@playwright/test";
import { addNewApiKeys } from "./add-new-api-keys";
import { adjustScreenView } from "./adjust-screen-view";
import { removeOldApiKeys } from "./remove-old-api-keys";
import { selectGptModel } from "./select-gpt-model";
import { updateOldComponents } from "./update-old-components";

export async function initialGPTsetup(
  page: Page,
  options?: {
    skipAdjustScreenView?: boolean;
    skipUpdateOldComponents?: boolean;
    skipRemoveOldApiKeys?: boolean;
    skipAddNewApiKeys?: boolean;
    skipSelectGptModel?: boolean;
  },
) {
  if (!options?.skipAdjustScreenView) {
    await adjustScreenView(page);
  }
  if (!options?.skipUpdateOldComponents) {
    await updateOldComponents(page);
  }
  if (!options?.skipRemoveOldApiKeys) {
    await removeOldApiKeys(page);
  }
  if (!options?.skipAddNewApiKeys) {
    await addNewApiKeys(page);
  }
  if (!options?.skipSelectGptModel) {
    await selectGptModel(page);
  }
}
