import type { Locator, Page } from "@playwright/test";
import { expect } from "../fixtures";
import { TEXTS } from "../utils/constants/texts";
import { adjustScreenView } from "./adjust-screen-view";
import { unselectNodes } from "./unselect-nodes";

const PREFERRED_OPENAI_MODELS = [
  "gpt-4o-mini",
  "gpt-4.1-mini",
  "gpt-4o",
  "gpt-4.1",
];

const findPreferredOpenAiModelInDropdown = async (page: Page) => {
  for (const modelName of PREFERRED_OPENAI_MODELS) {
    if ((await page.getByTestId(`${modelName}-option`).count()) > 0) {
      return modelName;
    }
  }
  return null;
};

const findPreferredOpenAiModelInProviderModal = async (page: Page) => {
  for (const modelName of PREFERRED_OPENAI_MODELS) {
    const toggle = page.getByTestId(`llm-toggle-${modelName}`);
    if ((await toggle.count()) > 0) {
      return modelName;
    }
  }
  return null;
};

const openModelDropdown = async (page: Page, model: Locator) => {
  await adjustScreenView(page);
  await expect(model).toBeVisible({ timeout: 10000 });
  await model.click();
  await page.waitForSelector('[role="listbox"]', { timeout: 10000 });
};

const enablePreferredOpenAiModel = async (page: Page) => {
  await page.getByTestId("manage-model-providers").click();
  await page.waitForSelector("text=Model providers", { timeout: 30000 });

  await page.getByTestId("provider-item-OpenAI").click();
  await page.waitForTimeout(500);

  const apiKeyInput = page.getByTestId(
    "provider-variable-input-OPENAI_API_KEY",
  );
  const checkExistingKey = await page.getByTestId("input-end-icon").count();
  if (checkExistingKey === 0 && (await apiKeyInput.count()) > 0) {
    await apiKeyInput.fill(process.env.OPENAI_API_KEY!);
    await page.waitForSelector("text=OpenAI Api Key Saved", {
      timeout: 30000,
    });
  }

  const modelName = await findPreferredOpenAiModelInProviderModal(page);
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

export const selectGptModel = async (page: Page) => {
  const nodes = page.locator(".react-flow__node", {
    has: page.getByTestId("title-language model"),
  });

  const gptModelDropdownCount = await nodes.count();

  for (let i = 0; i < gptModelDropdownCount; i++) {
    const node = nodes.nth(i);
    try {
      await expect(node.getByTestId("model_model").last()).toBeVisible({
        timeout: 10000,
      });
    } catch {
      await node.click();
    }

    const model = (await node.getByTestId("model_model").last().isVisible())
      ? node.getByTestId("model_model").last()
      : page.getByTestId("model_model").last();

    await openModelDropdown(page, model);

    let modelName = await findPreferredOpenAiModelInDropdown(page);
    if (!modelName) {
      modelName = await enablePreferredOpenAiModel(page);
      await openModelDropdown(page, model);
      if ((await page.getByTestId(`${modelName}-option`).count()) === 0) {
        await page.getByTestId("refresh-model-list").click();
        await openModelDropdown(page, model);
      }
    }

    const selectedOption = page.getByTestId(`${modelName}-option`);
    await expect(selectedOption).toBeVisible({ timeout: 30000 });
    await selectedOption.dispatchEvent("click");

    if (i < gptModelDropdownCount - 1) {
      await unselectNodes(page);
    }
  }
};
