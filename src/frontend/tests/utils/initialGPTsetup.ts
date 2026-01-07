import type { Page } from "@playwright/test";
import { adjustScreenView } from "./adjust-screen-view";
import { selectGptModel } from "./select-gpt-model";
import { updateOldComponents } from "./update-old-components";
import { addOpenAiInputKey } from "./add-open-ai-input-key";

export async function initialGPTsetup(
  page: Page,
  options?: {
    skipAdjustScreenView?: boolean;
    skipUpdateOldComponents?: boolean;
    skipSelectGptModel?: boolean;
    skipAddOpenAiInputKey?: boolean;
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
  if (!options?.skipAddOpenAiInputKey) {
    await addOpenAiInputKey(page);
  }
}
