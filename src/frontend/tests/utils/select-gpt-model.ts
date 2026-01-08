import type { Page } from "@playwright/test";

const MODEL_OPTION_TESTID = "gpt-4o-mini-option";
const MODEL_TOGGLE_TESTID = "llm-toggle-gpt-4o-mini";
const LISTBOX_TIMEOUT = 10000;
const MODAL_TIMEOUT = 30000;
const SHORT_DELAY = 500;

async function configureOpenAIProvider(page: Page): Promise<boolean> {
  await page.getByTestId("manage-model-providers").click();
  await page.waitForSelector("text=Model providers", { timeout: MODAL_TIMEOUT });
  await page.getByTestId("provider-item-OpenAI").click();
  await page.waitForTimeout(SHORT_DELAY);

  const hasExistingKey = (await page.getByTestId("input-end-icon").count()) > 0;

  if (!hasExistingKey) {
    await page
      .getByPlaceholder("Add API key")
      .fill(process.env.OPENAI_API_KEY!);
    await page.waitForSelector("text=OpenAI Api Key Saved", {
      timeout: MODAL_TIMEOUT,
    });
    await page.getByTestId(MODEL_TOGGLE_TESTID).click();
    await page.getByText("Close").last().click();
    return false;
  }

  await page.waitForTimeout(SHORT_DELAY);
  const isModelEnabled = await page.getByTestId(MODEL_TOGGLE_TESTID).isChecked();
  if (!isModelEnabled) {
    await page.getByTestId(MODEL_TOGGLE_TESTID).click();
  }
  await page.getByText("Close").last().click();
  return true;
}

async function selectModelFromDropdown(
  page: Page,
  dropdownTestId: string,
  index: number,
): Promise<void> {
  await page.getByTestId(dropdownTestId).nth(index).click();
  await page.waitForSelector('[role="listbox"]', { timeout: LISTBOX_TIMEOUT });

  const hasModelOption = (await page.getByTestId(MODEL_OPTION_TESTID).count()) > 0;
  await page.waitForTimeout(SHORT_DELAY);

  if (!hasModelOption) {
    const needsReopen = await configureOpenAIProvider(page);
    if (needsReopen) {
      await page.getByTestId(dropdownTestId).nth(index).click();
    }
  }

  await page.waitForTimeout(SHORT_DELAY);
  await page.getByTestId(MODEL_OPTION_TESTID).click();
}

export const selectGptModel = async (page: Page): Promise<void> => {
  const modelDropdownCount = await page.getByTestId("model_model").count();
  const modelNameDropdownCount = await page
    .getByTestId("model_model_name")
    .count();

  for (let i = 0; i < modelDropdownCount; i++) {
    await selectModelFromDropdown(page, "model_model", i);
  }

  for (let i = 0; i < modelNameDropdownCount; i++) {
    await selectModelFromDropdown(page, "model_model_name", i);
  }
};
