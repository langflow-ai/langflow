import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  NO_DESTINATION,
  readyToCopy,
  startOver,
} from "../../utils/migration-walk";

test(
  "an admin copies the database, stops a copy and copies again",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    // A copy needs changes paused, which refuses every change to the instance, so this walk can't share a server with other specs.
    test.skip(Boolean(NO_DESTINATION), NO_DESTINATION);
    await awaitBootstrapTest(page, { skipModal: true });
    const instance = await startOver(page);
    test.skip(
      instance.database.type !== "sqlite",
      "Only an instance on SQLite has a database to copy.",
    );
    await readyToCopy(page, instance);

    try {
      await page.goto("/settings/migration");
      const copy = page.getByTestId("migration-step-copy_database");
      await copy.getByRole("button", { name: "Copy the database" }).click();

      // The copy is the server's own process. The page shows what it says while it runs.
      await expect(copy.getByRole("button", { name: "Stop" })).toBeVisible();
      await expect(copy).toContainText(
        /Checking what there is to copy…|Preparing the new database…|Rows: [\d,]+ of [\d,]+|Tables: [\d,]+\./,
        { timeout: 120000 },
      );

      // A page that is loaded again finds the run where it is and follows it to its end.
      await page.reload();
      await expect(copy).toContainText(/Tables: [\d,]+\. Rows: [\d,]+\./, {
        timeout: 120000,
      });
      const copied = (
        await (await page.request.get("/api/v1/migration")).json()
      ).record.steps.copy_database.report;
      expect(copied.ok).toBe(true);
      expect(copied.rows_copied).toBeGreaterThan(0);

      // Copied again and stopped on the way: the step says so, and nothing of that copy counts.
      const again = copy.getByRole("button", { name: "Copy again" });
      // A copy that ended while the page was loading shows closed, and its title opens it.
      if (!(await again.isVisible()))
        await copy.getByRole("button", { name: "Copy the database" }).click();
      await again.click();
      await copy.getByRole("button", { name: "Stop" }).click();
      await page
        .getByRole("dialog", { name: "Stop copying?" })
        .getByRole("button", { name: "Stop", exact: true })
        .click();
      await expect(copy.getByRole("alert")).toContainText(
        "Stopped before it finished. Run it again.",
        { timeout: 60000 },
      );

      await again.click();
      await expect(copy).toContainText(/Tables: [\d,]+\. Rows: [\d,]+\./, {
        timeout: 120000,
      });
      await expect(copy.getByRole("alert")).toHaveCount(0);
    } finally {
      // A walk that stops midway must leave no copy running and no pause on.
      await startOver(page);
    }
  },
);
