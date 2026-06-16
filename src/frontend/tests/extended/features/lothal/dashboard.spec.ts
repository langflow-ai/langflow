// Epic B.15 — e2e coverage for the Lothal dashboard.
//
// Runs against the real auto-login-off backend: sign in as the superuser, then
// exercise the live project CRUD (Story B.2). No mocking — the empty state is
// made real by deleting the user's projects through the API first, and the card
// assertions are scoped to a uniquely named project the test creates.

import { expect, test } from "../../../fixtures";
import {
  deleteAllProjects,
  loginAsSuperuser,
} from "../../../utils/lothal-login";

test.describe(
  "Lothal dashboard",
  { tag: ["@release", "@api", "@database", "@lothal"] },
  () => {
    test.beforeEach(async ({ page }) => {
      await loginAsSuperuser(page);
    });

    test("empty state when there are no projects", async ({ page }) => {
      // Real clean slate.
      await deleteAllProjects(page);
      await page.goto("/lothal");
      await expect(page.getByText("No projects yet")).toBeVisible({
        timeout: 30000,
      });
    });

    test("create → card → open → delete", async ({ page }) => {
      const name = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

      await page.goto("/lothal");
      await expect(page.getByText("Your workspace")).toBeVisible({
        timeout: 30000,
      });

      // Create via the modal — on success the app opens the new workspace.
      await page.getByRole("button", { name: "New project" }).first().click();
      const dialog = page.getByRole("dialog", { name: "New project" });
      await expect(dialog).toBeVisible();
      await dialog.getByLabel("Project name").fill(name);
      await dialog.getByRole("button", { name: "Create" }).click();
      await page.waitForURL("**/lothal/*", { timeout: 30000 });

      // Back on the dashboard the project shows as a card with its phase
      // StatusDot ("clarifying" for a fresh CLARIFICATION project) and a
      // relative timestamp.
      await page.goto("/lothal");
      const card = page.getByRole("button").filter({ hasText: name });
      await expect(card).toBeVisible({ timeout: 30000 });
      await expect(card.getByText("clarifying")).toBeVisible();
      await expect(card.getByText("just now")).toBeVisible();

      // Opening the card lands in the workspace for that project.
      await card.click();
      await page.waitForURL("**/lothal/*", { timeout: 30000 });
      await expect(page).not.toHaveURL(/\/lothal$/);

      // Delete from the card (the confirm() guard is auto-accepted).
      await page.goto("/lothal");
      const card2 = page.getByRole("button").filter({ hasText: name });
      await expect(card2).toBeVisible({ timeout: 30000 });
      page.on("dialog", (d) => d.accept());
      await card2.hover();
      await card2.getByRole("button", { name: `Delete ${name}` }).click();

      await expect(page.getByText(name, { exact: true })).toBeHidden({
        timeout: 30000,
      });
    });
  },
);
