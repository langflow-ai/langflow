import type { Page } from "@playwright/test";
import { openStarterProject } from "./flow/open-starter-project";
import { initialGPTsetup } from "./initialGPTsetup";

type InitialGptSetupOptions = Parameters<typeof initialGPTsetup>[1];

/**
 * Open a starter-project template by name, then apply the standard GPT setup
 * (update components, select the GPT model, add the OpenAI key). This is the
 * open-template + configure prelude repeated across the per-template
 * integration specs. Pair with `runPlaygroundPrompt` to exercise the flow.
 */
export async function seedGptTemplate(
  page: Page,
  name: string,
  options?: InitialGptSetupOptions,
): Promise<void> {
  await openStarterProject(page, name);
  await initialGPTsetup(page, options);
}
