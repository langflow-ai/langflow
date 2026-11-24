import { expect, test } from "../../fixtures";
import { addFlowToTestOnEmptyLangflow } from "../../utils/add-flow-to-test-on-empty-langflow";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { TEXTS } from "../../utils/constants/texts";

test(
  "user should be able to download a flow or a component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await adjustScreenView(page);

    await page.getByText(TEXTS.componentChatInput, { exact: true }).click();
    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("icon-SaveAll").first().click();

    if (await page.getByTestId("replace-button").isVisible()) {
      await page.getByTestId("replace-button").click();
    }

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
    });

    const exitButton = await page
      .getByText(TEXTS.exit, { exact: true })
      .count();

    if (exitButton > 0) {
      await page.getByText(TEXTS.exit, { exact: true }).click();
    }

    await page.getByTestId("icon-ChevronLeft").last().click();
    await page.getByTestId("home-dropdown-menu").nth(0).click();
    await page.getByTestId("btn-download-json").last().click();
    await expect(page.getByText("Export").first()).toBeVisible();
    await expect(page.getByTestId("modal-export-button")).toBeVisible();
    await page.getByTestId("modal-export-button").click();
    await expect(page.getByText(/.*exported successfully/)).toBeVisible({
      timeout: 10000,
    });

    await page.getByText("Flows", { exact: true }).click();
    await page.getByTestId("home-dropdown-menu").nth(0).click();
    await page.getByTestId("btn-download-json").last().click();
    await expect(page.getByText("Export").first()).toBeVisible();
    await expect(page.getByTestId("modal-export-button")).toBeVisible();
    await page.getByTestId("modal-export-button").click();
    await expect(page.getByText(/.*exported successfully/).last()).toBeVisible({
      timeout: 10000,
    });

    if (await page.getByText(TEXTS.labelComponents).first().isVisible()) {
      await page.getByText(TEXTS.labelComponents, { exact: true }).click();
      await page.getByTestId("home-dropdown-menu").nth(0).click();
      await page.getByTestId("btn-download-json").last().click();
      await expect(
        page.getByText(/.*exported successfully/).last(),
      ).toBeVisible({
        timeout: 10000,
      });
    }
  },
);

test(
  "user should be able to upload a flow or a component",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });
    const countEmptyButton = await page
      .getByTestId("new_project_btn_empty_page")
      .count();
    if (countEmptyButton > 0) {
      await addFlowToTestOnEmptyLangflow(page);
    }
    await page.getByTestId("upload-project-button").last().click();
  },
);

test(
  "user should be able to duplicate a flow or a component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    await adjustScreenView(page);

    await page.getByText(TEXTS.componentChatInput, { exact: true }).click();
    await page.getByTestId("more-options-modal").click();

    await page.getByTestId("icon-SaveAll").first().click();

    if (await page.getByTestId("replace-button").isVisible()) {
      await page.getByTestId("replace-button").click();
    }

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
    });

    const exitButton = await page
      .getByText(TEXTS.exit, { exact: true })
      .count();

    if (exitButton > 0) {
      await page.getByText(TEXTS.exit, { exact: true }).click();
    }

    const replaceButton = await page.getByTestId("replace-button").isVisible();

    if (replaceButton) {
      await page.getByTestId("replace-button").click();
    }

    await page.getByTestId("icon-ChevronLeft").last().click();
    await page.getByTestId("home-dropdown-menu").nth(1).click();
    await page.getByTestId("btn-duplicate-flow").last().click();

    await expect(page.getByText("Flow duplicated successfully")).toBeVisible({
      timeout: 10000,
    });
  },
);
