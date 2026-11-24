import type { Page } from "@playwright/test";

const OPENAI_API_KEY_INPUT_TEST_IDS = [
  "popover-anchor-input-openai_api_key",
  "popover-anchor-input-api_key",
];

export const addOpenAiInputKey = async (page: Page) => {
  for (const testId of OPENAI_API_KEY_INPUT_TEST_IDS) {
    const numberOfOpenAiFields = await page.getByTestId(testId).count();

    for (let i = 0; i < numberOfOpenAiFields; i++) {
      const openAiInput = page.getByTestId(testId).nth(i);
      const inputValue = await openAiInput.inputValue();

      if (!inputValue) {
        await openAiInput.fill(process.env.OPENAI_API_KEY!);
      }

      await page.waitForTimeout(500);
    }
  }
};
