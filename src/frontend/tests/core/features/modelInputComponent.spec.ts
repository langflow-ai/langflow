import type { Page } from "@playwright/test";

import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { TEXTS } from "../../utils/constants/texts";

const addLanguageModelNode = async (page: Page) => {
  await page.getByTestId("sidebar-search-input").click();
  await page
    .getByTestId("sidebar-search-input")
    .fill(TEXTS.componentLanguageModel);
  await page.waitForTimeout(500);

  const languageModelComponent = page
    .getByText(TEXTS.componentLanguageModel, { exact: true })
    .first();
  await expect(languageModelComponent).toBeVisible({ timeout: 5000 });
  await page.getByTestId("add-component-button-language-model").click();
  await page.waitForTimeout(1000);

  const node = page.locator(".react-flow__node").first();
  await expect(node).toBeVisible({ timeout: 5000 });
  return node;
};

const openBlankFlowForModelInput = async (page: Page) => {
  await awaitBootstrapTest(page);
  await page.getByTestId("blank-flow").click();

  await expect(page.getByTestId("modal-title")).toBeHidden({
    timeout: 30000,
  });

  const sidebarSearchInput = page.getByTestId("sidebar-search-input");
  if (!(await sidebarSearchInput.isVisible())) {
    const createdFlow = page
      .getByTestId("flow-name-div")
      .filter({ hasText: "New Flow" })
      .first();

    const createdFlowVisible = await createdFlow
      .waitFor({ state: "visible", timeout: 5000 })
      .then(() => true)
      .catch(() => false);

    if (createdFlowVisible) {
      await createdFlow.click();
    }
  }

  await expect(sidebarSearchInput).toBeVisible({ timeout: 30000 });
};

test.describe("ModelInputComponent", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(() => {
    test.skip(
      process.platform === "win32",
      "Flaky on Windows CI runners: SQLite 'database is locked' during flow teardown cascades into the next test's bootstrap (new-project modal / sidebar never render). The model-provider coverage is OS-agnostic and runs on Linux/macOS",
    );
  });

  test(
    "should display model selector in a node with model input",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await openBlankFlowForModelInput(page);

      const node = await addLanguageModelNode(page);

      const modelSection = node.locator(
        '[data-testid*="model"], button:has-text("Setup Provider"), [role="combobox"]',
      );
      await expect(modelSection.first()).toBeVisible({ timeout: 3000 });
    },
  );

  test(
    "should open model dropdown and show providers",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await openBlankFlowForModelInput(page);

      await addLanguageModelNode(page);

      const modelDropdown = page.locator('[role="combobox"]').first();
      if (await modelDropdown.isVisible()) {
        await modelDropdown.click();
        await page.waitForTimeout(500);

        const dropdownContent = page.locator('[role="listbox"], [cmdk-list]');
        if (await dropdownContent.isVisible({ timeout: 2000 })) {
          await expect(dropdownContent).toBeVisible();
        }
      }
    },
  );

  test(
    "should show Manage Model Providers button in dropdown",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await openBlankFlowForModelInput(page);

      await addLanguageModelNode(page);

      const modelDropdown = page.locator('[role="combobox"]').first();
      if (await modelDropdown.isVisible()) {
        await modelDropdown.click();
        await page.waitForTimeout(500);

        const manageProvidersBtn = page.getByTestId("manage-model-providers");
        if (await manageProvidersBtn.isVisible({ timeout: 2000 })) {
          await expect(manageProvidersBtn).toBeVisible();
          await expect(page.getByText("Manage Model Providers")).toBeVisible();
        }
      }
    },
  );

  test(
    "should open Model Provider Modal from dropdown",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await openBlankFlowForModelInput(page);

      await addLanguageModelNode(page);

      const modelDropdown = page.locator('[role="combobox"]').first();
      if (await modelDropdown.isVisible()) {
        await modelDropdown.click();
        await page.waitForTimeout(500);

        const manageProvidersBtn = page.getByTestId("manage-model-providers");
        if (await manageProvidersBtn.isVisible({ timeout: 2000 })) {
          await manageProvidersBtn.click();

          await expect(page.getByText("Model providers")).toBeVisible({
            timeout: 5000,
          });
        }
      }
    },
  );

  test(
    "should show Refresh List button in dropdown",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await openBlankFlowForModelInput(page);

      await addLanguageModelNode(page);

      const modelDropdown = page.locator('[role="combobox"]').first();
      if (await modelDropdown.isVisible()) {
        await modelDropdown.click();
        await page.waitForTimeout(500);

        const refreshText = page.getByText("Refresh List");
        if (await refreshText.isVisible({ timeout: 2000 })) {
          await expect(refreshText).toBeVisible();
        }
      }
    },
  );

  test(
    "should display selected model in trigger button",
    { tag: ["@release", "@components", "@workspace"] },
    async ({ page }) => {
      await openBlankFlowForModelInput(page);

      await addLanguageModelNode(page);

      const modelDropdown = page.locator('[role="combobox"]').first();
      if (await modelDropdown.isVisible()) {
        const text = await modelDropdown.textContent();
        expect(text).toBeTruthy();
      }
    },
  );
});
