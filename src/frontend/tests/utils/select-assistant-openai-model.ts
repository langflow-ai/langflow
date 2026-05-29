import type { Page } from "@playwright/test";
import { expect } from "../fixtures";

import { TEXTS } from "../utils/constants/texts";

const PREFERRED_OPENAI_MODELS = [
  "gpt-4o-mini",
  "gpt-4.1-mini",
  "gpt-4o",
  "gpt-4.1",
];

const getAssistantModelItem = (page: Page, modelName: string) =>
  page.getByRole("menuitem").filter({ hasText: modelName }).first();

const findPreferredModelInAssistantMenu = async (page: Page) => {
  for (const modelName of PREFERRED_OPENAI_MODELS) {
    if ((await getAssistantModelItem(page, modelName).count()) > 0) {
      return modelName;
    }
  }
  return null;
};

const findPreferredModelInProviderModal = async (page: Page) => {
  for (const modelName of PREFERRED_OPENAI_MODELS) {
    if ((await page.getByTestId(`llm-toggle-${modelName}`).count()) > 0) {
      return modelName;
    }
  }
  return null;
};

const enablePreferredOpenAiModel = async (page: Page) => {
  await page.getByTestId("assistant-manage-model-providers").click();
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
  }

  const modelName = await findPreferredModelInProviderModal(page);
  if (!modelName) {
    throw new Error(
      `None of the preferred OpenAI models were available to enable: ${PREFERRED_OPENAI_MODELS.join(
        ", ",
      )}`,
    );
  }

  const toggle = page.getByTestId(`llm-toggle-${modelName}`);
  if (!(await toggle.isChecked())) {
    await toggle.click();
  }

  await page.getByText(TEXTS.close).last().click();
  return modelName;
};

export const selectAssistantOpenAiModel = async (page: Page) => {
  const selector = page.getByTestId("assistant-model-selector");
  await expect(selector).toBeVisible({ timeout: 15000 });
  await selector.click();

  let modelName = await findPreferredModelInAssistantMenu(page);
  if (!modelName) {
    modelName = await enablePreferredOpenAiModel(page);
    await expect(selector).toBeVisible({ timeout: 30000 });
    await selector.click();

    if ((await getAssistantModelItem(page, modelName).count()) === 0) {
      await page.getByTestId("assistant-refresh-model-list").click();
      await expect(selector).toBeVisible({ timeout: 30000 });
      await selector.click();
    }
  }

  const modelItem = getAssistantModelItem(page, modelName);
  await expect(modelItem).toBeVisible({ timeout: 30000 });
  await modelItem.click();
  await expect(selector).toContainText(modelName);
};
