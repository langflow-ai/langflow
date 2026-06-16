// Epic B.15 — e2e coverage for the Lothal signup page (client-side validation).
//
// Runs against the real auto-login-off backend. The signup page renders for
// anonymous visitors regardless of whether the backend accepts new accounts;
// this covers the purely client-side guard: the inline "Passwords don't match."
// message appears and the submit button stays disabled, so a mismatched form can
// never be sent. The server-side gate (signups disabled in this deployment) is
// covered by signup-disabled.spec.ts.

import { expect, test } from "../../../fixtures";

test.describe(
  "Lothal signup",
  { tag: ["@release", "@api", "@database", "@lothal"] },
  () => {
    test("password mismatch blocks submit", async ({ page }) => {
      await page.goto("/signup");

      await expect(page.getByText("Create your account")).toBeVisible({
        timeout: 30000,
      });

      const create = page.getByRole("button", { name: "Create account" });
      // Disabled to begin with (empty form).
      await expect(create).toBeDisabled();

      await page.getByPlaceholder("Choose a username").fill("captain");
      await page.getByPlaceholder("Create a password").fill("anchor-1234");
      await page.getByPlaceholder("Re-enter your password").fill("anchor-9999");

      // Inline validation appears and the button stays disabled.
      await expect(page.getByText("Passwords don't match.")).toBeVisible();
      await expect(create).toBeDisabled();

      // Fixing the confirmation clears the error and enables submit.
      await page.getByPlaceholder("Re-enter your password").fill("anchor-1234");
      await expect(page.getByText("Passwords don't match.")).toBeHidden();
      await expect(create).toBeEnabled();
    });
  },
);
