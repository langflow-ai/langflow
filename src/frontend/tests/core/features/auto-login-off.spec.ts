import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { renameFlow } from "../../utils/rename-flow";
import { zoomOut } from "../../utils/zoom-out";

test(
  "when auto_login is false, admin can CRUD user's and should see just your own flows",
  { tag: ["@release", "@api", "@database", "@mainpage"] },
  async ({ page }) => {
    await page.route("**/api/v1/auto_login", (route) => {
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          detail: { auto_login: false },
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

    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

    await page.getByPlaceholder("Username").fill("langflow");
    await page.getByPlaceholder("Password").fill("langflow");

    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });

    await page.getByRole("button", { name: "Sign In" }).click();

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

    await page.getByTestId("user-profile-settings").click();

    await page.getByText("Admin Page", { exact: true }).click();

    //CRUD an user
    await page.getByText("New User", { exact: true }).click();

    await page.getByPlaceholder("Username").last().fill(randomName);
    await page.locator('input[name="password"]').fill(randomPassword);
    await page.locator('input[name="confirmpassword"]').fill(randomPassword);

    await page.waitForSelector("#is_active", {
      timeout: 1500,
    });

    await page.locator("#is_active").click();

    await page.getByText("Save", { exact: true }).click();

    await page.waitForSelector("text=new user added", { timeout: 30000 });

    await expect(page.getByText(randomName, { exact: true })).toBeVisible({
      timeout: 2000,
    });

    await page.getByTestId("icon-Trash2").last().click();
    await page.getByText("Delete", { exact: true }).last().click();

    await page.waitForSelector("text=user deleted", { timeout: 30000 });

    await expect(page.getByText(randomName, { exact: true })).toBeVisible({
      timeout: 2000,
      visible: false,
    });

    await page.getByText("New User", { exact: true }).click();

    await page.getByPlaceholder("Username").last().fill(randomName);
    await page.locator('input[name="password"]').fill(randomPassword);
    await page.locator('input[name="confirmpassword"]').fill(randomPassword);

    await page.waitForSelector("#is_active", {
      timeout: 1500,
    });

    await page.locator("#is_active").click();

    await page.getByText("Save", { exact: true }).click();

    await page.waitForSelector("text=new user added", { timeout: 30000 });

    await page.getByPlaceholder("Username").last().fill(randomName);

    await page.getByTestId("icon-Pencil").last().click();

    await page.getByPlaceholder("Username").last().fill(secondRandomName);

    await page.getByText("Save", { exact: true }).click();

    await page.waitForSelector("text=user edited", { timeout: 30000 });

    await expect(page.getByText(secondRandomName, { exact: true })).toBeVisible(
      {
        timeout: 2000,
      },
    );

    //user must see just your own flows
    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

    await awaitBootstrapTest(page, { skipGoto: true });

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await adjustScreenView(page, { numberOfZoomOut: 1 });

    await renameFlow(page, { flowName: randomFlowName });

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
      state: "visible",
    });

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
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

    await page.getByText("Logout", { exact: true }).click();

    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

    await page.getByPlaceholder("Username").fill(secondRandomName);
    await page.getByPlaceholder("Password").fill(randomPassword);

    await page.waitForSelector("text=Sign in", {
      timeout: 1500,
    });

    await page.getByRole("button", { name: "Sign In" }).click();

    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

    expect(
      (
        await page.waitForSelector("text=Welcome to LangFlow", {
          timeout: 30000,
        })
      ).isVisible(),
    );

    await page.waitForTimeout(2000);

    await awaitBootstrapTest(page, { skipGoto: true });

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await adjustScreenView(page, { numberOfZoomOut: 2 });

    await renameFlow(page, { flowName: secondRandomFlowName });

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
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

    await page.getByText("Logout", { exact: true }).click();

    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

    await page.getByPlaceholder("Username").fill("langflow");
    await page.getByPlaceholder("Password").fill("langflow");

    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });

    await page.getByRole("button", { name: "Sign In" }).click();

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
