// Epic B.15 — e2e coverage for the Lothal workspace shell.
//
// Runs against the real auto-login-off backend: sign in, create a project, then
// assert the workspace it opens. A fresh project is in the CLARIFICATION phase,
// so the workspace should render:
//   • the project name + the PhaseStepper (all five phase labels)
//   • the chat column in its NotReady state — /messages is still a 501 stub, so
//     "The conversation isn't live yet" is shown (the live-501 path)
//   • the canvas placeholder for CLARIFICATION ("The diagram takes shape here").
// No mocking.

import { expect, test } from "../../../fixtures";
import { loginAsSuperuser } from "../../../utils/lothal-login";

test.describe(
  "Lothal workspace",
  { tag: ["@release", "@api", "@database", "@lothal"] },
  () => {
    test("renders phase stepper, chat NotReady, and canvas placeholder", async ({
      page,
    }) => {
      await loginAsSuperuser(page);

      const name = `e2e-ws-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

      // Create a project; the dashboard opens its workspace on success.
      await page.goto("/lothal");
      await expect(page.getByText("Your workspace")).toBeVisible({
        timeout: 30000,
      });
      await page.getByRole("button", { name: "New project" }).first().click();
      const dialog = page.getByRole("dialog", { name: "New project" });
      await expect(dialog).toBeVisible();
      await dialog.getByLabel("Project name").fill(name);
      await dialog.getByRole("button", { name: "Create" }).click();
      await page.waitForURL("**/lothal/*", { timeout: 30000 });

      // Top bar carries the project name.
      await expect(page.getByText(name, { exact: true })).toBeVisible({
        timeout: 30000,
      });

      // PhaseStepper — the five phase labels, in order.
      for (const label of [
        "Clarify",
        "Sketch",
        "Refine",
        "Generate",
        "Deliver",
      ]) {
        await expect(page.getByText(label, { exact: true })).toBeVisible();
      }

      // Chat column reflects the live 501 from /messages.
      await expect(
        page.getByText("The conversation isn't live yet"),
      ).toBeVisible({ timeout: 30000 });

      // Canvas placeholder for the clarification phase.
      await expect(
        page.getByText("The diagram takes shape here"),
      ).toBeVisible();
    });
  },
);
