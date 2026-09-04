import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import {
  createActiveUserViaApi,
  deleteUserViaApi,
  updateUserViaApi,
} from "../../utils/auth/manage-users-via-api";
import { TEXTS } from "../../utils/constants/texts";
import {
  openTemplatesModal,
  waitForNewProjectButton,
} from "../../utils/flow/new-project-flow";
import { submitLoginAndRequireSuccess } from "../../utils/login-langflow";
import { renameFlow } from "../../utils/rename-flow";

test(
  "when auto_login is false, admin can CRUD user's and should see just your own flows",
  { tag: ["@release", "@api", "@database"] },
  async ({ page }) => {
    await page.route("**/api/v1/auto_login", (route) => {
      route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({
          detail: {
            message: "Auto login is disabled.",
            auto_login: false,
          },
        }),
      });
    });

    await page.addInitScript(() => {
      window.process = window.process || {};

      const newEnv = { ...window.process.env, LANGFLOW_AUTO_LOGIN: "false" };

      Object.defineProperty(window.process, "env", {
        value: newEnv,
        writable: true,
        configurable: true,
      });

      sessionStorage.setItem("testMockAutoLogin", "true");
    });

    const randomName = Math.random().toString(36).substring(5);
    const randomPassword = Math.random().toString(36).substring(5);
    const secondRandomName = Math.random().toString(36).substring(5);
    const randomFlowName = Math.random().toString(36).substring(5);
    const secondRandomFlowName = Math.random().toString(36).substring(5);

    await page.goto("/");

    await expect(page.getByRole("button", { name: TEXTS.signIn })).toBeVisible({
      timeout: 30000,
    });

    await page
      .getByPlaceholder(TEXTS.placeholderUsername)
      .fill(TEXTS.authDefaultCredential);
    await page
      .getByPlaceholder(TEXTS.placeholderPassword)
      .fill(TEXTS.authDefaultPassword);

    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });

    await submitLoginAndRequireSuccess(page);

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await waitForNewProjectButton(page);

    // OSS Admin Page UI was removed; exercise the same admin user APIs
    // against the authenticated superuser session instead.
    const created = await createActiveUserViaApi(page, {
      username: randomName,
      password: randomPassword,
    });
    await deleteUserViaApi(page, created.id);

    const recreated = await createActiveUserViaApi(page, {
      username: randomName,
      password: randomPassword,
    });
    const renamed = await updateUserViaApi(page, recreated.id, {
      username: secondRandomName,
    });
    expect(renamed.username).toBe(secondRandomName);

    //user must see just your own flows
    await waitForNewProjectButton(page);

    await openTemplatesModal(page, {
      fromEmptyPage: await page
        .getByTestId("new_project_btn_empty_page")
        .isVisible(),
    });

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await adjustScreenView(page, { numberOfZoomOut: 1 });

    await renameFlow(page, { flowName: randomFlowName });

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
      state: "visible",
    });

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 1500,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="search-store-input"]:enabled', {
      timeout: 30000,
      state: "visible",
    });

    await expect(page.getByText(randomFlowName, { exact: true })).toBeVisible({
      timeout: 2000,
    });

    await page.waitForSelector("[data-testid='user-profile-settings']", {
      timeout: 1500,
    });

    await page.getByTestId("user-profile-settings").click();

    await page.evaluate(() => {
      sessionStorage.setItem("testMockAutoLogin", "true");
    });

    await page.getByText(TEXTS.logout, { exact: true }).click();

    await expect(page.getByRole("button", { name: TEXTS.signIn })).toBeVisible({
      timeout: 30000,
    });

    await page
      .getByPlaceholder(TEXTS.placeholderUsername)
      .fill(secondRandomName);
    await page.getByPlaceholder(TEXTS.placeholderPassword).fill(randomPassword);

    await submitLoginAndRequireSuccess(page);

    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });

    await waitForNewProjectButton(page);

    expect(
      (
        await page.waitForSelector("text=Welcome to LangFlow", {
          timeout: 30000,
        })
      ).isVisible(),
    );

    await page.waitForTimeout(2000);

    await openTemplatesModal(page, {
      fromEmptyPage: await page
        .getByTestId("new_project_btn_empty_page")
        .isVisible(),
    });

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await adjustScreenView(page, { numberOfZoomOut: 2 });

    await renameFlow(page, { flowName: secondRandomFlowName });

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="search-store-input"]:enabled', {
      timeout: 30000,
    });

    await expect(
      page.getByText(secondRandomFlowName, { exact: true }),
    ).toBeVisible({
      timeout: 2000,
    });

    await expect(page.getByText(randomFlowName, { exact: true })).toBeVisible({
      timeout: 2000,
      visible: false,
    });

    await page.getByTestId("user-profile-settings").click();

    await page.evaluate(() => {
      sessionStorage.setItem("testMockAutoLogin", "true");
    });

    await page.getByText(TEXTS.logout, { exact: true }).click();

    await expect(page.getByRole("button", { name: TEXTS.signIn })).toBeVisible({
      timeout: 30000,
    });

    await page
      .getByPlaceholder(TEXTS.placeholderUsername)
      .fill(TEXTS.authDefaultCredential);
    await page
      .getByPlaceholder(TEXTS.placeholderPassword)
      .fill(TEXTS.authDefaultPassword);

    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });

    await submitLoginAndRequireSuccess(page);

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[data-testid="search-store-input"]:enabled', {
      timeout: 30000,
    });

    expect(
      await page.getByText(secondRandomFlowName, { exact: true }).isVisible(),
    ).toBe(false);

    await expect(page.getByText(randomFlowName, { exact: true })).toBeVisible({
      timeout: 2000,
    });

    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });
  },
);
