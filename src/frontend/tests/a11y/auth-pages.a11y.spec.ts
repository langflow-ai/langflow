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

// State drivers navigate to a surface and drive it into the state to scan.
// They are theme-agnostic (the theme is forced by the caller before goto), so
// each state runs in BOTH light and dark below — IBM color-contrast checks are
// theme-dependent, so both modes must be scanned.
async function driveLoginEmpty(page: LangflowPage) {
  await disableAutoLogin(page);
  await page.goto("/login");
  await disableAnimations(page);
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
}

async function driveLoginValidation(page: LangflowPage) {
  await disableAutoLogin(page);
  await page.goto("/login");
  await disableAnimations(page);
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("alert").first()).toBeVisible();
}

async function driveLoginErrorToast(page: LangflowPage) {
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
}

async function driveSignupEmpty(page: LangflowPage) {
  await disableAutoLogin(page);
  await page.goto("/signup");
  await disableAnimations(page);
  await expect(page.getByRole("button", { name: /sign up/i })).toBeVisible();
}

async function driveSignupMismatch(page: LangflowPage) {
  await disableAutoLogin(page);
  await page.goto("/signup");
  await disableAnimations(page);
  await expect(page.getByRole("button", { name: /sign up/i })).toBeVisible();
  await page.getByLabel(/^Password/).fill("first-password");
  await page.getByLabel(/^Confirm your password/).fill("second-password");
  await page.getByLabel(/^Confirm your password/).blur();
  await expect(page.getByText(/Passwords do not match/)).toContainText(
    "Passwords do not match",
  );
}

async function driveSignupErrorToast(page: LangflowPage) {
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
}

async function driveAdminLoginEmpty(page: LangflowPage) {
  await disableAutoLogin(page);
  await page.goto("/login/admin");
  await disableAnimations(page);
  await expect(page.getByRole("button", { name: /login/i })).toBeVisible();
}

async function driveAdminLoginErrorToast(page: LangflowPage) {
  await disableAutoLogin(page);
  await mockLoginError(page);
  await page.goto("/login/admin");
  await disableAnimations(page);
  await expect(page.getByRole("button", { name: /login/i })).toBeVisible();
  await page.getByPlaceholder(/^Username$/).fill("alice");
  await page.getByPlaceholder(/^Password$/).fill("wrong-password");
  await page.getByRole("button", { name: /login/i }).click();
  await expect(page.getByText("Error signing in")).toBeVisible();
  await expect(page.getByText("Incorrect username or password.")).toBeVisible();
}

const AUTH_STATES: Array<{
  label: string;
  drive: (page: LangflowPage) => Promise<void>;
}> = [
  { label: "auth-login-empty", drive: driveLoginEmpty },
  { label: "auth-login-validation", drive: driveLoginValidation },
  { label: "auth-login-error-toast", drive: driveLoginErrorToast },
  { label: "auth-signup-empty", drive: driveSignupEmpty },
  { label: "auth-signup-mismatch", drive: driveSignupMismatch },
  { label: "auth-signup-error-toast", drive: driveSignupErrorToast },
  { label: "auth-admin-login-empty", drive: driveAdminLoginEmpty },
  { label: "auth-admin-login-error-toast", drive: driveAdminLoginErrorToast },
];

const THEMES: Array<{
  name: "light" | "dark";
  force: (page: LangflowPage) => Promise<void>;
  suffix: string;
  scanOptions?: { colorScheme: "dark" };
}> = [
  { name: "light", force: forceLightTheme, suffix: "" },
  {
    name: "dark",
    force: forceDarkTheme,
    suffix: "-dark",
    scanOptions: { colorScheme: "dark" },
  },
];

test.describe("auth page accessibility", () => {
  for (const theme of THEMES) {
    for (const state of AUTH_STATES) {
      test(
        `scans ${state.label} (${theme.name})`,
        { tag: ["@release"] },
        async ({ page }) => {
          await theme.force(page);
          await state.drive(page);
          if (theme.name === "dark") {
            await expect(page.locator("body")).toHaveClass(/dark/);
          }
          await page.runA11yScan(
            `${state.label}${theme.suffix}`,
            theme.scanOptions,
          );
        },
      );
    }
  }
});
