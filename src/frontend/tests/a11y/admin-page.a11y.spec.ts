import { expect, test } from "../fixtures";
import { TEXTS } from "../utils/constants/texts";
import type { LangflowPage } from "../utils/types";

async function disableAnimations(page: LangflowPage) {
  await page.addStyleTag({
    content: `
      *,
      *::before,
      *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        scroll-behavior: auto !important;
      }
    `,
  });
}

async function forceTheme(page: LangflowPage, dark: boolean) {
  await page.addInitScript((isDark) => {
    window.localStorage.setItem("themePreference", isDark ? "dark" : "light");
    window.localStorage.setItem("isDark", isDark ? "true" : "false");
  }, dark);
}

// `/admin` redirects to `/` whenever auto-login is active (see ProtectedAdminRoute).
// Reach it by mocking auto-login off and signing in as the seeded superuser,
// mirroring tests/core/features/auto-login-off.spec.ts.
async function loginAsAdmin(page: LangflowPage) {
  await page.route("**/api/v1/auto_login", (route) => {
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: { auto_login: false } }),
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

  await page.getByRole("button", { name: TEXTS.signIn }).click();
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });
}

// Navigate client-side via the UI menu — a full page.goto("/admin") reload would
// re-run addInitScript (re-mocking auto-login) and drop the signed-in admin session.
async function gotoAdminPage(page: LangflowPage) {
  await page.getByTestId("user-profile-settings").click();
  await page.getByText("Admin Page", { exact: true }).click();
  await expect(page.getByText("Admin Page", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await expect(page.getByRole("button", { name: /new user/i })).toBeVisible();
  // Wait for the user table to finish loading so scans are deterministic
  // (otherwise the scan can race the row render and miss table violations).
  await expect(page.locator("table tbody tr").first()).toBeVisible({
    timeout: 30000,
  });
  await disableAnimations(page);
}

test.describe("admin page accessibility", () => {
  test(
    "scans admin page",
    { tag: ["@release", "@api", "@database"] },
    async ({ page }) => {
      await forceTheme(page, false);
      await loginAsAdmin(page);
      await gotoAdminPage(page);
      await page.runA11yScan("admin-page-empty");
    },
  );

  test(
    "scans new user modal",
    { tag: ["@release", "@api", "@database"] },
    async ({ page }) => {
      await forceTheme(page, false);
      await loginAsAdmin(page);
      await gotoAdminPage(page);

      await page.getByRole("button", { name: /new user/i }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();
      await expect(
        dialog.getByRole("button", { name: /^Save$/ }),
      ).toBeVisible();
      await page.runA11yScan("admin-new-user-modal");
    },
  );

  test(
    "scans admin page in dark mode",
    { tag: ["@release", "@api", "@database"] },
    async ({ page }) => {
      await forceTheme(page, true);
      await loginAsAdmin(page);
      await gotoAdminPage(page);
      await expect(page.locator("body")).toHaveClass(/dark/);
      await page.runA11yScan("admin-page-dark", { colorScheme: "dark" });
    },
  );

  // Tab order / keyboard operability: the clear-search control used to be a
  // <div onClick> (unfocusable, WCAG 2.1.1). It must now be tab-reachable
  // right after the search field and activate with the keyboard.
  test(
    "clear-search is keyboard reachable and operable",
    { tag: ["@release", "@api", "@database"] },
    async ({ page }) => {
      await loginAsAdmin(page);
      await gotoAdminPage(page);

      const search = page.getByRole("textbox", { name: /search username/i });
      await search.fill("langflow");

      const clearButton = page.getByRole("button", { name: /clear search/i });
      await expect(clearButton).toBeVisible();

      // A single Tab from the search field lands on the clear button
      // (focus order matches visual order).
      await search.focus();
      await page.keyboard.press("Tab");
      await expect(clearButton).toBeFocused();

      // Enter activates it and clears the field.
      await page.keyboard.press("Enter");
      await expect(search).toHaveValue("");
    },
  );
});
