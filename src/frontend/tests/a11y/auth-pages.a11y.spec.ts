import { expect, test } from "../fixtures";
import type { LangflowPage } from "../utils/types";

async function disableAutoLogin(page: LangflowPage) {
  await page.route("**/api/v1/auto_login", (route) => {
    route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({
        detail: { message: "Auto login is disabled.", auto_login: false },
      }),
    });
  });
}

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

async function mockLoginError(page: LangflowPage) {
  await page.route("**/api/v1/login", (route) => {
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Incorrect username or password." }),
    });
  });
}

async function mockSignupError(page: LangflowPage) {
  await page.route("**/api/v1/users/", (route) => {
    route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({ detail: "This username is unavailable." }),
    });
  });
}

async function forceDarkTheme(page: LangflowPage) {
  await page.addInitScript(() => {
    window.localStorage.setItem("themePreference", "dark");
    window.localStorage.setItem("isDark", "true");
  });
}

async function forceLightTheme(page: LangflowPage) {
  await page.addInitScript(() => {
    window.localStorage.setItem("themePreference", "light");
    window.localStorage.setItem("isDark", "false");
  });
}

test.describe("auth page accessibility", () => {
  test("scans empty login", { tag: ["@a11y"] }, async ({ page }) => {
    await forceLightTheme(page);
    await disableAutoLogin(page);

    await page.goto("/login");
    await disableAnimations(page);
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
    await page.runA11yScan("auth-login-empty");
  });

  test("scans login validation", { tag: ["@a11y"] }, async ({ page }) => {
    await forceLightTheme(page);
    await disableAutoLogin(page);

    await page.goto("/login");
    await disableAnimations(page);
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByRole("alert").first()).toBeVisible();
    await page.runA11yScan("auth-login-validation");
  });

  test("scans login error toast", { tag: ["@a11y"] }, async ({ page }) => {
    await forceLightTheme(page);
    await disableAutoLogin(page);
    await mockLoginError(page);

    await page.goto("/login");
    await disableAnimations(page);
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
    await page.getByRole("textbox", { name: /^Username \*$/ }).fill("alice");
    await page.getByLabel(/^Password/).fill("wrong-password");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByText("Error signing in")).toBeVisible();
    await expect(
      page.getByText(
        "Incorrect username or password. Check your username and password, then try again.",
      ),
    ).toBeVisible();
    await page.runA11yScan("auth-login-error-toast");
  });

  test("scans empty signup", { tag: ["@a11y"] }, async ({ page }) => {
    await forceLightTheme(page);
    await disableAutoLogin(page);
    await page.goto("/signup");
    await disableAnimations(page);
    await expect(page.getByRole("button", { name: /sign up/i })).toBeVisible();
    await page.runA11yScan("auth-signup-empty");
  });

  test(
    "scans signup password mismatch",
    { tag: ["@a11y"] },
    async ({ page }) => {
      await forceLightTheme(page);
      await disableAutoLogin(page);

      await page.goto("/signup");
      await disableAnimations(page);
      await expect(
        page.getByRole("button", { name: /sign up/i }),
      ).toBeVisible();
      await page.getByLabel(/^Password/).fill("first-password");
      await page.getByLabel(/^Confirm your password/).fill("second-password");
      await page.getByLabel(/^Confirm your password/).blur();
      await expect(page.getByText(/Passwords do not match/)).toContainText(
        "Passwords do not match",
      );
      await page.runA11yScan("auth-signup-mismatch");
    },
  );

  test("scans signup error toast", { tag: ["@a11y"] }, async ({ page }) => {
    await forceLightTheme(page);
    await disableAutoLogin(page);
    await mockSignupError(page);

    await page.goto("/signup");
    await disableAnimations(page);
    await expect(page.getByRole("button", { name: /sign up/i })).toBeVisible();
    await page.getByRole("textbox", { name: /^Username \*$/ }).fill("alice");
    await page.getByLabel(/^Password/).fill("same-password");
    await page.getByLabel(/^Confirm your password/).fill("same-password");
    await page.getByRole("button", { name: /sign up/i }).click();
    await expect(page.getByText("Error signing up")).toBeVisible();
    await expect(
      page.getByText(
        "This username is unavailable. Use a different username or contact an administrator if you already have an account.",
      ),
    ).toBeVisible();
    await page.runA11yScan("auth-signup-error-toast");
  });

  test("scans login in dark mode", { tag: ["@a11y"] }, async ({ page }) => {
    await forceDarkTheme(page);
    await disableAutoLogin(page);

    await page.goto("/login");
    await disableAnimations(page);
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
    await expect(page.locator("body")).toHaveClass(/dark/);

    await page.runA11yScan("auth-login-dark-empty", { colorScheme: "dark" });
  });
});
