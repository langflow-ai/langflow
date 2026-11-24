import type { Locator, Page } from "@playwright/test";
import { expect } from "../fixtures";
import { TEXTS } from "../utils/constants/texts";
import { adjustScreenView } from "./adjust-screen-view";
import { unselectNodes } from "./unselect-nodes";

const OPENAI_PROVIDER = "OpenAI";

const PREFERRED_OPENAI_MODELS = [
  "gpt-4o-mini",
  "gpt-4.1-mini",
  "gpt-4o",
  "gpt-4.1",
];

const getOpenAiModelOptionTestId = (modelName: string) =>
  `${OPENAI_PROVIDER}-${modelName}-option`;

const findPreferredOpenAiModelInDropdown = async (page: Page) => {
  for (const modelName of PREFERRED_OPENAI_MODELS) {
    if (
      (await page.getByTestId(getOpenAiModelOptionTestId(modelName)).count()) >
      0
    ) {
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

// The model dropdown footer buttons ("Manage providers", "Refresh list") render
// inside the in-canvas popover, which is drawn without a portal
// (PopoverContentWithoutPortal). When the language-model node sits low on the
// canvas the footer can be clipped, or shift while the model list settles, so a
// plain click() fails Playwright's "visible, enabled and stable" actionability
// check and times out. Nudge the button into view and dispatch the click
// directly — the same workaround already used for the model option below.
const clickModelDropdownFooter = async (page: Page, testId: string) => {
  const button = page.getByTestId(testId);
  await button.waitFor({ state: "attached", timeout: 10000 });
  await button.scrollIntoViewIfNeeded().catch(() => {});
  await button.dispatchEvent("click");
};

const configureOpenAiInProviderModal = async (page: Page) => {
  await page.getByTestId("provider-item-OpenAI").click();
  await page.waitForTimeout(500);

  const apiKeyInput = page.getByTestId(
    "provider-variable-input-OPENAI_API_KEY",
  );
  const checkExistingKey = await page.getByTestId("input-end-icon").count();
  if (checkExistingKey === 0 && (await apiKeyInput.count()) > 0) {
    await apiKeyInput.fill(process.env.OPENAI_API_KEY!);
    // The provider modal stopped autosaving on input when it gained the
    // explicit Save flow (#11446): the key is validated with a live provider
    // call and persisted only after the Save button is clicked. The success
    // toast ("<Provider> Configuration Saved") is deferred until the post-save
    // model refetch settles, so once it shows the model toggles below are
    // ready to interact with.
    await page.getByTestId("provider-save-button").click();
    await page.waitForSelector(`text=${OPENAI_PROVIDER} Configuration Saved`, {
      timeout: 60000,
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

const enablePreferredOpenAiModel = async (page: Page) => {
  await clickModelDropdownFooter(page, "manage-model-providers");
  await page.waitForSelector("text=Model providers", { timeout: 30000 });
  return configureOpenAiInProviderModal(page);
};

const languageModelNodes = (page: Page) =>
  page.locator(".react-flow__node", {
    has: page.locator(
      [
        '[data-testid="title-language model"]',
        '[data-testid="title-agent"]',
        '[data-testid="title-batch run"]',
        '[data-testid="title-structured output"]',
      ].join(", "),
    ),
  });

// On a backend with no configured provider, ModelInput renders a "Setup
// Provider" call-to-action instead of the model dropdown, so the
// `model_model` trigger doesn't exist and the selection loop below would
// silently skip every node — leaving the model empty and the run failing
// with "A model selection is required". Configure OpenAI through the
// provider manager (the CTA opens the same modal) so the dropdown mounts.
const setupProviderIfNeeded = async (page: Page) => {
  const modelNodes = languageModelNodes(page);
  if ((await modelNodes.count()) === 0) return;
  if (
    (await modelNodes
      .filter({ has: page.getByTestId("model_model") })
      .count()) > 0
  ) {
    return;
  }

  const setupTrigger = modelNodes
    .getByText("Setup Provider", { exact: true })
    .first();
  if ((await setupTrigger.count()) === 0) return;

  await setupTrigger.click();
  await page.waitForSelector("text=Model providers", { timeout: 30000 });
  await configureOpenAiInProviderModal(page);

  // Closing the modal refetches providers/enabled models; the dropdown
  // replaces the CTA once the refresh settles.
  await expect(page.getByTestId("model_model").first()).toBeVisible({
    timeout: 30000,
  });
};

export const selectGptModel = async (page: Page) => {
  await setupProviderIfNeeded(page);

  const nodes = languageModelNodes(page).filter({
    has: page.getByTestId("model_model"),
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
      if (
        (await page
          .getByTestId(getOpenAiModelOptionTestId(modelName))
          .count()) === 0
      ) {
        await clickModelDropdownFooter(page, "refresh-model-list");
        await openModelDropdown(page, model);
      }
    }

    const selectedOption = page.getByTestId(
      getOpenAiModelOptionTestId(modelName),
    );
    await expect(selectedOption).toBeVisible({ timeout: 30000 });
    await selectedOption.dispatchEvent("click");

    if (i < gptModelDropdownCount - 1) {
      await unselectNodes(page);
    }
  }
};
