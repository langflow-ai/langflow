import { expect, test } from "@playwright/test";
import { renameFlow } from "../../utils/rename-flow";

test(
  "flow state should be properly cleaned up between user sessions",
  { tag: ["@release", "@api", "@database"] },
  async ({ page }) => {
    // Disable auto login
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
      const newEnv = {
        ...window.process.env,
        LANGFLOW_AUTO_LOGIN: "false",
        LANGFLOW_NEW_USER_IS_ACTIVE: "true",
      };
      Object.defineProperty(window.process, "env", {
        value: newEnv,
        writable: true,
        configurable: true,
      });
      sessionStorage.setItem("testMockAutoLogin", "true");
    });

    // Create random usernames, passwords and flow names for the test
    const userAName = "user_a_" + Math.random().toString(36).substring(5);
    const userAPassword = "pass_a_" + Math.random().toString(36).substring(5);
    const userAFlowName = "flow_a_" + Math.random().toString(36).substring(5);

    // Log in as admin and create test user
    await page.goto("/");
    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });
    await page.getByPlaceholder("Username").fill("langflow");
    await page.getByPlaceholder("Password").fill("langflow");
    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });
    await page.getByRole("button", { name: "Sign In" }).click();

    // Create User A
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });
    await page.getByTestId("user-profile-settings").click();
    await page.getByText("Admin Page", { exact: true }).click();
    await page.getByText("New User", { exact: true }).click();
    await page.getByPlaceholder("Username").last().fill(userAName);
    await page.locator('input[name="password"]').fill(userAPassword);
    await page.locator('input[name="confirmpassword"]').fill(userAPassword);
    await page.waitForSelector("#is_active", { timeout: 1500 });
    await page.locator("#is_active").click();
    await expect(page.locator("#is_active")).toBeChecked();
    await page.getByText("Save", { exact: true }).click();
    await page.waitForSelector("text=new user added", { timeout: 30000 });

    // Log out from admin
    await page.getByTestId("icon-ChevronLeft").first().click();
    await page.waitForSelector("[data-testid='user-profile-settings']", {
      timeout: 1500,
    });
    await page.getByTestId("user-profile-settings").click();
    await page.evaluate(() => {
      sessionStorage.setItem("testMockAutoLogin", "true");
    });
    await page.getByText("Logout", { exact: true }).click();

    // ---- USER A SESSION ----

    // Log in as User A
    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });
    await page.getByPlaceholder("Username").fill(userAName);
    await page.getByPlaceholder("Password").fill(userAPassword);
    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });
    await page.getByRole("button", { name: "Sign In" }).click();

    // Create a flow for User A
    await page.waitForSelector('[id="new-project-btn"]', { timeout: 30000 });
    // Check that User A starts with an empty flows list
    expect(
      (
        await page.waitForSelector("text=Welcome to LangFlow", {
          timeout: 30000,
        })
      ).isVisible(),
    );

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    try {
      await page.getByTestId("new_project_btn_empty_page").click();
    } catch (_error) {
      await page.getByTestId("new-project-btn").click();
    }

    await page.waitForSelector('[data-testid="modal-title"]', {
      timeout: 3000,
    });
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.waitForSelector('[data-testid="fit_view"]', { timeout: 30000 });

    await renameFlow(page, { flowName: userAFlowName });

    await page.getByTestId("icon-ChevronLeft").first().click();

    // Verify User A can see their flow
    await page.waitForSelector('[data-testid="search-store-input"]:enabled', {
      timeout: 30000,
    });
    await expect(page.getByText(userAFlowName, { exact: true })).toBeVisible({
      timeout: 2000,
    });

    // Log out User A
    await page.getByTestId("user-profile-settings").click();
    await page.evaluate(() => {
      sessionStorage.setItem("testMockAutoLogin", "true");
    });
    await page.getByText("Logout", { exact: true }).click();

    // ---- ADMIN SESSION AGAIN ----

    // Log in as admin again
    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });
    await page.getByPlaceholder("Username").fill("langflow");
    await page.getByPlaceholder("Password").fill("langflow");
    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });
    await page.getByRole("button", { name: "Sign In" }).click();

    // Verify admin can't see User A's flow
    await expect(page.getByText(userAFlowName, { exact: true })).toBeVisible({
      timeout: 2000,
      visible: false,
    });

    // Cleanup
    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });
  },
);
