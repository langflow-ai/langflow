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
});
