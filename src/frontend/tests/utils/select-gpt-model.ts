import type { Page } from "@playwright/test";

export const selectGptModel = async (page: Page) => {
  const gptModelDropdownCount = await page.getByTestId("model_model").count();

  for (let i = 0; i < gptModelDropdownCount; i++) {
    await page.getByTestId("model_model").nth(i).click();
    await page.waitForSelector('[role="listbox"]', { timeout: 10000 });

    const gptOMiniOption = await page.getByTestId("gpt-4o-mini-option").count();

    if (gptOMiniOption === 0) {
      await page.getByTestId("manage-model-providers").click();
      await page.waitForSelector("text=Model providers", { timeout: 30000 });

      await page.getByTestId("provider-item-OpenAI").click();

      const checkExistingKey = await page.getByTestId("input-end-icon").count();
      if (checkExistingKey === 0) {
        await page
          .getByPlaceholder("Add API key")
          .fill(process.env.OPENAI_API_KEY!);
        await page.waitForSelector("text=OpenAI Api Key Saved", {
          timeout: 30000,
        });
        await page.getByTestId("llm-toggle-gpt-4o-mini").click();
        await page.getByText("Close").last().click();
      } else {
        const isChecked = await page
          .getByTestId("llm-toggle-gpt-4o-mini")
          .isChecked();
        if (!isChecked) {
          await page.getByTestId("llm-toggle-gpt-4o-mini").click();
        }
        await page.getByText("Close").last().click();
        await page.getByTestId("model_model").nth(i).click();
      }
    }

    await page.getByTestId("gpt-4o-mini-option").click();
  }
};
