import fs from "node:fs";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { NO_DESTINATION, prepare, startOver } from "../../utils/migration-walk";

test(
  "an admin pauses changes, backs up this instance and turns changes back on",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    // Pausing refuses every change to the instance, so this walk can't share a server with other specs.
    test.skip(Boolean(NO_DESTINATION), NO_DESTINATION);
    await awaitBootstrapTest(page, { skipModal: true });
    await prepare(page, await startOver(page));
    // A change to try from outside the page. It writes nothing, whether it is let through or not.
    const change = async () =>
      (
        await page.request.post("/api/v1/validate/code", {
          data: { code: "x = 1" },
        })
      ).status();

    try {
      await page.goto("/settings/migration");
      const pause = page.getByTestId("migration-step-pause");
      await pause.getByRole("button", { name: "Pause changes" }).click();
      await page
        .getByRole("dialog", { name: "Pause changes now?" })
        .getByRole("button", { name: "Pause", exact: true })
        .click();

      // Paused: the banner comes up, and the page checks this instance again by itself.
      const banner = page.getByText("Changes are paused on this instance.");
      await expect(banner).toBeVisible();
      await expect(pause).toContainText(
        /Running the check again… Checking: \d+ of \d+/,
      );
      await expect(pause).toContainText(/Paused .+ by /, { timeout: 120000 });
      expect(await change()).toBe(503);

      // That check passed, so the backup opens and takes the focus.
      const backup = page.getByTestId("migration-step-backup");
      await expect(
        backup.getByRole("heading", { name: "Back up this instance" }),
      ).toBeFocused();
      const confirm = backup.getByRole("button", {
        name: "I've backed up everything",
      });
      await expect(confirm).toBeDisabled();
      const download = page.waitForEvent("download");
      await backup
        .getByRole("button", { name: "Download the database" })
        .click();
      const copy = await download;
      expect(copy.suggestedFilename()).toMatch(/^langflow-backup-\d{8}\.db$/);
      // The copy starts with the header every SQLite database has.
      expect(
        fs
          .readFileSync(await copy.path())
          .subarray(0, 15)
          .toString(),
      ).toBe("SQLite format 3");
      await expect(backup.getByText(/^Downloaded .+\.$/)).toBeVisible();
      // With no place named, the browser's own message asks for one, and nothing is confirmed.
      const location = backup.getByLabel("Where is the backup?");
      await confirm.click();
      await expect(location).toBeFocused();
      expect(
        await location.evaluate(
          (field: HTMLInputElement) => field.validationMessage,
        ),
      ).not.toBe("");
      await expect(confirm).toBeVisible();
      // Pasted with a space on each side, which the server drops.
      await location.fill(" s3://backups/langflow ");
      await confirm.click();
      await expect(backup).toContainText(
        /Backed up .+ to s3:\/\/backups\/langflow\./,
      );

      // The banner stays in view down at the end of the page, where the way back is.
      const recovery = page.locator("details", {
        hasText: "If something goes wrong",
      });
      await recovery.getByText("If something goes wrong").click();
      await expect(banner).toBeInViewport();
      await recovery
        .getByRole("button", { name: "Turn changes back on" })
        .click();
      const asked = page.getByRole("dialog", { name: "Turn changes back on?" });
      await expect(asked).toContainText("out of date");
      await asked.getByRole("button", { name: "Resume", exact: true }).click();

      // Changes are back on, and what was backed up during the pause no longer counts.
      await expect(banner).toHaveCount(0);
      await expect(
        pause.getByRole("button", { name: "Pause changes" }),
      ).toBeVisible();
      await expect(backup.getByRole("button")).toHaveCount(0);
      expect(await change()).not.toBe(503);
    } finally {
      // A walk that stops midway must not leave the instance refusing changes, nor past its first steps.
      await startOver(page);
    }
  },
);
