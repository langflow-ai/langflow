// Epic B.15 — e2e coverage for the signup-disabled gate (audit Fix #3).
//
// The real deployment runs with LANGFLOW_ENABLE_SIGNUP=false (invite-only), so
// POST /api/v1/users/ answers 403 { detail: "Sign up is currently disabled." }.
// A 403 normally drives the axios response interceptor down the refresh→logout
// path; the fix makes the interceptor bypass that for the signup-create request
// so the error surfaces to the page instead of logging the visitor out. This is
// the only end-to-end coverage of that interceptor branch — and here it runs
// against the genuine backend gate, no mocking.

import { expect, test } from "../../../fixtures";

test.describe(
  "Lothal signup disabled gate",
  { tag: ["@release", "@api", "@database", "@lothal"] },
  () => {
    test("403 surfaces a toast and keeps the user on /signup", async ({
      page,
    }) => {
      await page.goto("/signup");
      await expect(page.getByText("Create your account")).toBeVisible({
        timeout: 30000,
      });

      await page
        .getByPlaceholder("Choose a username")
        .fill(`turned-away-${Date.now()}`);
      await page.getByPlaceholder("Create a password").fill("anchor-1234");
      await page.getByPlaceholder("Re-enter your password").fill("anchor-1234");
      await page.getByRole("button", { name: "Create account" }).click();

      // The backend's message is surfaced as a toast…
      await expect(
        page.getByText("Sign up is currently disabled."),
      ).toBeVisible({ timeout: 30000 });

      // …and the interceptor did NOT log the visitor out / bounce to /login.
      await expect(page).toHaveURL(/\/signup$/);
      await expect(page.getByText("Create your account")).toBeVisible();
    });
  },
);
