import type { Page } from "@playwright/test";
import { expect } from "../fixtures";

export const selectGptModel = async (page: Page) => {
  const node = page.locator(".react-flow__node", { has: page.getByTestId("title-language model") });
  await node.click();
  await expect(page.getByTestId("model_model")).toBeVisible({timeout: 3000});

  const gptModelDropdownCount = await page.getByTestId("model_model").count();

  for (let i = 0; i < gptModelDropdownCount; i++) {
    await page.getByTestId("model_model").nth(i).click();
    await page.waitForSelector('[role="listbox"]', { timeout: 10000 });

    const gptOMiniOption = await page.getByTestId("gpt-4o-mini-option").count();

    await page.waitForTimeout(500);

    if (gptOMiniOption === 0) {
      await page.getByTestId("manage-model-providers").click();
      await page.waitForSelector("text=Model providers", { timeout: 30000 });

      await page.getByTestId("provider-item-OpenAI").click();
      await page.waitForTimeout(500);

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
        await page.waitForTimeout(500);

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
    await page.waitForTimeout(500);
    await page.getByTestId("gpt-4o-mini-option").click();
  }
};
