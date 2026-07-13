import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import {
  openTemplatesModal,
  waitForNewProjectButton,
} from "../../utils/flow/new-project-flow";
import { renameFlow } from "../../utils/rename-flow";

test(
  "flow state should be properly cleaned up between user sessions",
  { tag: ["@release", "@api", "@database"] },
  async ({ page }) => {
    test.skip(
      process.platform === "win32",
      "Flaky on Windows CI runners due to multi-session workload; covered by Linux/macOS runs",
    );

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
    const userAName = "user_a_" + crypto.randomUUID().substring(0, 8);
    const userAPassword = "pass_a_" + crypto.randomUUID().substring(0, 8);
    const userAFlowName = "flow_a_" + crypto.randomUUID().substring(0, 8);

    // Log in as admin and create test user
    await page.goto("/");
    await page.waitForSelector(`text=${TEXTS.authSignInHeader}`, {
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
    await Promise.all([
      page.waitForResponse(
        (response) =>
          response.url().includes("/api/v1/login") && response.status() === 200,
        { timeout: 60000 },
      ),
      page.getByRole("button", { name: TEXTS.signIn }).click(),
    ]);

    // mainpage_title only renders after the homepage data finishes loading,
    // and on slower runners (Windows CI) this can outlast a 60s wait.
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 90000,
    });
    await page.getByTestId("user-profile-settings").click();
    await page.getByText("Admin Page", { exact: true }).click();
    await page.getByText("New User", { exact: true }).click();
    await page
      .getByPlaceholder(TEXTS.placeholderUsername)
      .last()
      .fill(userAName);
    await page.locator('input[name="password"]').fill(userAPassword);
    await page.locator('input[name="confirmpassword"]').fill(userAPassword);
    await page.waitForSelector("#is_active", { timeout: 1500 });
    await page.locator("#is_active").click();
    await expect(page.locator("#is_active")).toBeChecked();
    await page.getByText(TEXTS.save, { exact: true }).click();
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
    await page.getByText(TEXTS.logout, { exact: true }).click();

    // ---- USER A SESSION ----

    // Log in as User A
    await page.waitForSelector(`text=${TEXTS.authSignInHeader}`, {
      timeout: 30000,
    });
    await page.getByPlaceholder(TEXTS.placeholderUsername).fill(userAName);
    await page.getByPlaceholder(TEXTS.placeholderPassword).fill(userAPassword);
    await page.evaluate(() => {
      sessionStorage.removeItem("testMockAutoLogin");
    });
    await Promise.all([
      page.waitForResponse(
        (response) =>
          response.url().includes("/api/v1/login") && response.status() === 200,
        { timeout: 60000 },
      ),
      page.getByRole("button", { name: TEXTS.signIn }).click(),
    ]);

    // Create a flow for User A
    await waitForNewProjectButton(page, { timeout: 60000 });
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

    // The empty-page CTA now routes through the welcome overlay before the
    // templates modal opens; openTemplatesModal handles both the overlay and
    // direct-modal paths.
    await openTemplatesModal(page, {
      fromEmptyPage: true,
      modalTimeout: 30000,
    });

    // Use blank-flow instead of the Basic Prompting template. The template
    // path provisions multiple components on the backend and, on Windows CI
    // shards under load, the new-flow canvas can stay un-mounted past 240s.
    // This cleanup test only needs *some* flow owned by the user, so a blank
    // flow is equivalent in scope while avoiding the Windows-specific stall.
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 60000,
    });

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
    await page.getByText(TEXTS.logout, { exact: true }).click();

    // ---- ADMIN SESSION AGAIN ----

    // Log in as admin again
    await page.waitForSelector(`text=${TEXTS.authSignInHeader}`, {
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
    await Promise.all([
      page.waitForResponse(
        (response) =>
          response.url().includes("/api/v1/login") && response.status() === 200,
        { timeout: 60000 },
      ),
      page.getByRole("button", { name: TEXTS.signIn }).click(),
    ]);

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
