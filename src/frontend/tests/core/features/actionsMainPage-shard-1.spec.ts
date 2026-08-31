import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";
import { routeTestScopedDefaultFlowNames } from "../../utils/flow/route-test-scoped-default-flow-names";

test.beforeEach(async ({ page }, testInfo) => {
  await routeTestScopedDefaultFlowNames(page, testInfo, "actions-main");
});

test("select and delete a flow", { tag: ["@release"] }, async ({ page }) => {
  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page
    .getByRole("heading", { name: TEXTS.templateBasicPrompting })
    .click();

  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
    timeout: 5000,
  });

  await page.getByTestId("home-dropdown-menu").first().click();
  await page.waitForSelector('[data-testid="icon-Trash2"]', {
    timeout: 1000,
  });
  // click on the delete button
  await page.getByText(TEXTS.delete).last().click();
  await expect(page.getByText("This can't be undone.")).toBeVisible({
    timeout: 1000,
  });

  //confirm the deletion in the modal
  await page.getByText(TEXTS.delete).last().click();

  await expect(
    page.getByText("Selected items deleted successfully"),
  ).toBeVisible();
});

test("search flows", { tag: ["@release"] }, async ({ page }) => {
  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page
    .getByRole("heading", { name: TEXTS.templateBasicPrompting })
    .click();

  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await expect(page.getByTestId(TID.newProjectBtn)).toBeVisible();
  await openTemplatesModal(page);
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Memory Chatbot" }).click();

  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();
  await openTemplatesModal(page);
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Document Q&A" }).click();

  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();
  await page.getByPlaceholder("Search flows").fill("Memory Chatbot");
  await expect(page.getByText("Memory Chatbot", { exact: true })).toBeVisible();
  await expect(page.getByText("Document Q&A", { exact: true })).toBeHidden();
  await expect(
    page.getByText(TEXTS.templateBasicPrompting, { exact: true }),
  ).toBeHidden();
});

test("search components", { tag: ["@release"] }, async ({ page }) => {
  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page
    .getByRole("heading", { name: TEXTS.templateBasicPrompting })
    .click();

  await adjustScreenView(page, { numberOfZoomOut: 2 });

  await page.getByText(TEXTS.componentChatInput).first().click();
  await page.waitForSelector('[data-testid="more-options-modal"]', {
    timeout: 1000,
  });
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.keyboard.press("Escape");
  await page
    .getByText("Prompt", {
      exact: true,
    })
    .first()
    .click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.keyboard.press("Escape");

  await page.getByTestId("title-Language Model").click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.keyboard.press("Escape");

  const sidebarSearch = page.getByTestId("sidebar-search-input");
  await expect(sidebarSearch).toBeVisible();
  await sidebarSearch.fill("Chat Input");

  await expect(page.getByTestId("saved_componentsChat Input")).toBeVisible();
  await expect(page.getByTestId("saved_componentsPrompt")).toBeHidden();
  await expect(page.getByTestId("saved_componentsLanguage Model")).toBeHidden();
});
