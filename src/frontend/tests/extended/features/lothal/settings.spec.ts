// Epic B.15 — e2e coverage for the Lothal settings page.
//
// Runs against the real auto-login-off backend: sign in, then exercise:
//   • appearance persistence — theme + density choices are stored by
//     LothalSurface (localStorage) and survive a full reload.
//   • sign out — clears the session, so the protected settings route bounces to
//     /login. No mocking.
//
// Each Playwright test gets a fresh browser context, so persisted appearance
// from one test never leaks into another.

import { expect, test } from "../../../fixtures";
import { loginAsSuperuser } from "../../../utils/lothal-login";

test.describe(
  "Lothal settings",
  { tag: ["@release", "@api", "@database", "@lothal"] },
  () => {
    test.beforeEach(async ({ page }) => {
      await loginAsSuperuser(page);
    });

    test("theme + density persist across reload", async ({ page }) => {
      await page.goto("/lothal/settings");
      await expect(page.getByText("Appearance")).toBeVisible({
        timeout: 30000,
      });

      const light = page.getByRole("button", { name: "Light", exact: true });
      const compact = page.getByRole("button", { name: "compact" });

      await light.click();
      await compact.click();
      await expect(light).toHaveAttribute("aria-pressed", "true");
      await expect(compact).toHaveAttribute("aria-pressed", "true");

      await page.reload();
      await expect(page.getByText("Appearance")).toBeVisible({
        timeout: 30000,
      });

      // The choices survived the reload.
      await expect(
        page.getByRole("button", { name: "Light", exact: true }),
      ).toHaveAttribute("aria-pressed", "true");
      await expect(
        page.getByRole("button", { name: "Dark", exact: true }),
      ).toHaveAttribute("aria-pressed", "false");
      await expect(
        page.getByRole("button", { name: "compact" }),
      ).toHaveAttribute("aria-pressed", "true");
    });

    test("sign out ends the session", async ({ page }) => {
      await page.goto("/lothal/settings");
      await expect(page.getByText("Account")).toBeVisible({ timeout: 30000 });

      await page.getByRole("button", { name: "Sign out" }).click();

      // The session is cleared, so the protected settings route bounces to login.
      await page.waitForURL("**/login**", { timeout: 30000 });
      await expect(page.getByText("Welcome back")).toBeVisible({
        timeout: 30000,
      });
    });
  },
);
