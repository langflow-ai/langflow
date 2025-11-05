import type { Page } from "playwright/test";

export async function addNewApiKeys(page: Page) {
  const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
  const openaiApiKeyInput = page.getByTestId(
    "popover-anchor-input-openai_api_key",
  );

  const isApiKeyInputVisible = await apiKeyInput.count();
  const isOpenaiApiKeyInputVisible = await openaiApiKeyInput.count();

  if (isApiKeyInputVisible > 0) {
    for (let i = 0; i < isApiKeyInputVisible; i++) {
      await apiKeyInput.nth(i).fill(process.env.OPENAI_API_KEY ?? "");
    }
  }

  if (isOpenaiApiKeyInputVisible > 0) {
    for (let i = 0; i < isOpenaiApiKeyInputVisible; i++) {
      await openaiApiKeyInput.nth(i).fill(process.env.OPENAI_API_KEY ?? "");
    }
  }
}
