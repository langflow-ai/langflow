// Epic B.15 — e2e coverage for the Lothal login funnel.
//
// Runs against a real auto-login-off backend (see playwright.lothal.config.ts) —
// the actual deployment condition. No mocking. The funnel is: public landing
// ("/") → "Log in" → "/login" → submit creds → "/lothal" (the projects
// dashboard). With no explicit ?redirect the login page defaults its post-login
// destination to /lothal, so a plain landing CTA lands on the dashboard.

import { expect, test } from "../../../fixtures";

test.describe(
  "Lothal login funnel",
  { tag: ["@release", "@api", "@database", "@lothal"] },
  () => {
    test("landing CTA → /login → sign in → /lothal", async ({ page }) => {
      // Public front door.
      await page.goto("/");
      await expect(
        page.getByRole("button", { name: "Sign up", exact: true }).first(),
      ).toBeVisible({ timeout: 30000 });

      // Landing CTA → login page.
      await page
        .getByRole("button", { name: "Log in", exact: true })
        .first()
        .click();
      await page.waitForURL("**/login");
      await expect(page.getByText("Welcome back")).toBeVisible({
        timeout: 30000,
      });

      // Sign in with the real superuser the backend provisions.
      await page.getByPlaceholder("Your username").fill("langflow");
      await page.getByPlaceholder("Your password").fill("langflow");
      const loginResponse = page.waitForResponse(
        (r) =>
          r.url().includes("/api/v1/login") && r.request().method() === "POST",
        { timeout: 30000 },
      );
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await loginResponse;

      // With no explicit ?redirect, the login page defaults to /lothal.
      await page.waitForURL("**/lothal", { timeout: 30000 });
      await expect(page.getByText("Your workspace")).toBeVisible({
        timeout: 30000,
      });
      await expect(
        page.getByRole("button", { name: "New project" }).first(),
      ).toBeVisible();
    });
  },
);
