import { Page } from "playwright/test";

export async function addNewApiKeys(page: Page) {
  const apiKeyInput = page.getByTestId("popover-anchor-input-api_key");
  const isApiKeyInputVisible = await apiKeyInput.count();

  if (isApiKeyInputVisible > 0) {
    for (let i = 0; i < isApiKeyInputVisible; i++) {
      await apiKeyInput.nth(i).fill(process.env.OPENAI_API_KEY ?? "");
    }
  }
}
