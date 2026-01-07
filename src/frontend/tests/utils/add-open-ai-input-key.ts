import type { Page } from "@playwright/test";

export const addOpenAiInputKey = async (page: Page) => {
  const numberOfOpenAiFields = await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .count();

  for (let i = 0; i < numberOfOpenAiFields; i++) {
    const openAiInput = page
      .getByTestId("popover-anchor-input-openai_api_key")
      .nth(i);
    const inputValue = await openAiInput.inputValue();

    if (!inputValue) {
      await openAiInput.fill(process.env.OPENAI_API_KEY!);
    }

    await page.waitForTimeout(500);
  }
};
