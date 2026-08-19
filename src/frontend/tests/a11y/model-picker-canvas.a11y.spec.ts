import type { Page, Route } from "@playwright/test";
import { expect, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TEXTS } from "../utils/constants/texts";
import { TIMEOUTS } from "../utils/constants/timeouts";
import { openFlowCard } from "../utils/flow/open-flow-card";

// This spec exists to cover, in a real browser, the three riskiest
// behaviours in the ModelInputComponent a11y fix that jsdom cannot
// falsify: requestAnimationFrame-driven refocus on popover open,
// imperative tabindex mutation across a live option list on arrow-key
// navigation, and Tab-order escape from the option list to the Refresh
// button. The jsdom suite (ModelInputComponent.test.tsx) already covers
// the same assertions against a mocked DOM; this spec is the live-DOM
// counterpart the a11y review asked for.

const mockProviders = [
  {
    provider: "OpenAI",
    is_enabled: true,
    is_configured: true,
    models: [
      { model_name: "gpt-4", metadata: { model_type: "llm" } },
      { model_name: "gpt-3.5-turbo", metadata: { model_type: "llm" } },
    ],
  },
  {
    provider: "Anthropic",
    is_enabled: true,
    is_configured: true,
    models: [{ model_name: "claude-3-opus", metadata: { model_type: "llm" } }],
  },
];

const mockEnabledModels = {
  OpenAI: { "gpt-4": true, "gpt-3.5-turbo": true },
  Anthropic: { "claude-3-opus": true },
};

async function mockModelCatalog(page: Page) {
  await page.route(/\/api\/v1\/models(\?.*)?$/, async (route: Route) => {
    await route.fulfill({ json: mockProviders });
  });

  await page.route(
    /\/api\/v1\/models\/enabled_models$/,
    async (route: Route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({ json: { disabled_models: [] } });
        return;
      }
      await route.fulfill({ json: { enabled_models: mockEnabledModels } });
    },
  );
}

async function openBlankFlowForModelInput(page: Page) {
  await awaitBootstrapTest(page);
  await page.getByTestId("blank-flow").click();

  await expect(page.getByTestId("modal-title")).toBeHidden({
    timeout: TIMEOUTS.standard,
  });

  const sidebarSearchInput = page.getByTestId("sidebar-search-input");
  if (!(await sidebarSearchInput.isVisible())) {
    const createdFlow = page
      .getByTestId("flow-name-div")
      .filter({ hasText: "New Flow" })
      .first();

    const createdFlowVisible = await createdFlow
      .waitFor({ state: "visible", timeout: TIMEOUTS.short })
      .then(() => true)
      .catch(() => false);

    if (createdFlowVisible) {
      await openFlowCard(page, "New Flow");
    }
  }

  await expect(sidebarSearchInput).toBeVisible({ timeout: TIMEOUTS.standard });
}

async function addLanguageModelNode(page: Page) {
  await page.getByTestId("sidebar-search-input").click();
  await page
    .getByTestId("sidebar-search-input")
    .fill(TEXTS.componentLanguageModel);
  await page.waitForTimeout(500);

  const languageModelComponent = page
    .getByText(TEXTS.componentLanguageModel, { exact: true })
    .first();
  await expect(languageModelComponent).toBeVisible({ timeout: TIMEOUTS.short });
  await page.getByTestId("add-component-button-language-model").click();
  await page.waitForTimeout(1000);

  const node = page.locator(".react-flow__node").first();
  await expect(node).toBeVisible({ timeout: TIMEOUTS.short });
  return node;
}

test.describe("Model picker canvas accessibility", () => {
  test.beforeEach(() => {
    test.skip(
      process.platform === "win32",
      "Flaky on Windows CI runners: SQLite 'database is locked' during flow teardown cascades into the next test's bootstrap. Same skip as modelInputComponent.spec.ts.",
    );
  });

  test(
    "focus lands on the previously-selected model, arrow keys move focus, and Tab escapes to Refresh",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await mockModelCatalog(page);
      await openBlankFlowForModelInput(page);
      const node = await addLanguageModelNode(page);

      // Target the model field by its own accessible name (the field
      // label, e.g. "Language Model") rather than positional order — the
      // node can render other role="combobox" elements (its own action
      // menu, other fields), and picking "the first one" risked silently
      // grabbing the wrong control instead of failing loudly.
      const combobox = node.getByRole("combobox", {
        name: TEXTS.componentLanguageModel,
      });
      await expect(combobox).toBeVisible({ timeout: TIMEOUTS.short });

      // Work with whatever options actually render (mocked or real,
      // whichever data source the environment resolves) rather than a
      // hardcoded model name — getModelOptionTestId's own convention
      // (`${provider}-${modelName}-option`) is all we rely on. What
      // matters for this regression is that the selected option is *not*
      // the first one in the list.
      await combobox.click();
      // Scoped to the listbox (cmdk's CommandList role) so this can't
      // accidentally pick up an unrelated "-option" testid elsewhere on
      // the page.
      const optionLocator = page
        .getByRole("listbox")
        .locator('[data-testid$="-option"]');
      await expect(optionLocator.first()).toBeVisible({
        timeout: TIMEOUTS.medium,
      });
      const optionCount = await optionLocator.count();
      test.skip(
        optionCount < 3,
        "Need at least 3 rendered model options to exercise a non-first selection plus an ArrowUp move — got fewer than that from whatever data source (mocked or real) this environment resolved.",
      );

      const lastOption = optionLocator.last();
      const lastOptionTestId = await lastOption.getAttribute("data-testid");
      // cmdk's CommandItem carries `data-value="${provider}::${name}"` —
      // read the model name off it so we can confirm the trigger's
      // displayed value actually updated before reopening, rather than
      // guessing at a fixed wait.
      const lastOptionValue = await lastOption.getAttribute("data-value");
      const lastOptionModelName = lastOptionValue?.split("::").at(-1) ?? "";
      await lastOption.click();

      // setOpen(false) closes the popover synchronously, but the parent's
      // `value` prop (which decides which option gets tabindex="0" on the
      // next open) updates on a later render — reopening immediately can
      // race that update and land on stale selection state. Wait for the
      // popover to actually close and the trigger to display the newly
      // selected model before reopening.
      await expect(page.getByRole("listbox")).toBeHidden({
        timeout: TIMEOUTS.medium,
      });
      await expect(combobox).toContainText(lastOptionModelName, {
        timeout: TIMEOUTS.medium,
      });

      // Reopen and assert focus lands on the option that's actually
      // selected (last in the list), not the first option in the list.
      await combobox.click();
      const reselectedOption = page.getByTestId(lastOptionTestId!);
      await expect(reselectedOption).toBeVisible({ timeout: TIMEOUTS.medium });
      await expect(reselectedOption).toBeFocused({ timeout: TIMEOUTS.medium });

      // Arrow key navigation must move real DOM focus, not just cmdk's
      // internal highlighted/aria-selected state.
      await page.keyboard.press("ArrowUp");
      const secondToLastOptionTestId = await optionLocator
        .nth(optionCount - 2)
        .getAttribute("data-testid");
      const secondToLastOption = page.getByTestId(secondToLastOptionTestId!);
      await expect(secondToLastOption).toBeFocused({
        timeout: TIMEOUTS.medium,
      });

      // Tabbing out of the option list must land on the Refresh button,
      // not skip over the whole list (roving tabindex regression).
      await page.keyboard.press("Tab");
      const refreshButton = page.getByTestId("refresh-model-list");
      await expect(refreshButton).toBeFocused({ timeout: TIMEOUTS.medium });

      await page.runA11yScan("model-picker-popover-open-non-first-selected");
    },
  );
});
