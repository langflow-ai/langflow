import fs from "node:fs";
import path from "node:path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  NO_DESTINATION,
  readyToCopy,
  runCopy,
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

test(
  "an admin tries the copies of knowledge bases and files, then makes them",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(Boolean(NO_DESTINATION), NO_DESTINATION);
    await awaitBootstrapTest(page, { skipModal: true });
    let instance = await startOver(page);
    if (!instance.files.local) {
      // A file on this server, so the move has files to copy.
      await page.request.post("/api/v2/files", {
        multipart: {
          file: {
            name: "migration-walk.txt",
            mimeType: "text/plain",
            buffer: Buffer.from("moved"),
          },
        },
      });
      instance = await startOver(page);
    }
    await readyToCopy(page, instance);
    // The two copies work on the database the new instance will run on, which the first copy fills.
    if (instance.database.type === "sqlite")
      await runCopy(page, "copy_database");

    try {
      await page.goto("/settings/migration");
      const bases = page.getByTestId("migration-step-copy_knowledge_bases");
      const files = page.getByTestId("migration-step-copy_files");

      if (instance.knowledge_bases.local) {
        // A test run says what a copy would do, and completes nothing: the files still wait.
        await bases.getByRole("button", { name: "Test run" }).click();
        await expect(bases).toContainText(
          /Test run: nothing was copied\. To copy: [\d,]+\./,
          { timeout: 120000 },
        );
        await expect(files.getByRole("button")).toHaveCount(0);

        await bases
          .getByRole("button", { name: "Copy knowledge bases" })
          .click();
        await expect(bases).toContainText(/Copied: [\d,]+ of [\d,]+/, {
          timeout: 300000,
        });
        // That step is done, so the next one opens and takes the focus.
        await expect(
          files.getByRole("heading", { name: "Copy files" }),
        ).toBeFocused();
      } else {
        await expect(bases).toContainText(
          "Not needed: no knowledge bases are stored on this server.",
        );
      }

      await files.getByRole("button", { name: "Test run" }).click();
      await expect(files).toContainText(/Test run: nothing was copied\./, {
        timeout: 120000,
      });
      await files.getByRole("button", { name: "Copy files" }).click();
      await expect(files).toContainText(/Copied: [\d,]+ of [\d,]+/, {
        timeout: 300000,
      });

      const { steps, record } = await (
        await page.request.get("/api/v1/migration")
      ).json();
      expect(
        steps.find((step: { id: string }) => step.id === "copy_files").state,
      ).toBe("done");
      expect(record.steps.copy_files.report.ok).toBe(true);
    } finally {
      await startOver(page);
    }
  },
);

test(
  "an admin accepts a file that has nothing to copy",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(Boolean(NO_DESTINATION), NO_DESTINATION);
    await awaitBootstrapTest(page, { skipModal: true });
    const instance = await startOver(page);
    // A file the database lists, with its bytes taken off this server's disk for the walk. The file stays
    // from one walk to the next: deleted, it would leave the destination with a row this instance no longer has.
    const listed: { name: string; id: string; path: string }[] = await (
      await page.request.get("/api/v2/files")
    ).json();
    const lost =
      listed.find((file) => file.name === "walk-gone") ??
      (await (
        await page.request.post("/api/v2/files", {
          multipart: {
            file: {
              name: "walk-gone.txt",
              mimeType: "text/plain",
              buffer: Buffer.from("gone"),
            },
          },
        })
      ).json());
    const bytes = path.join(instance.files.folder, lost.path);
    fs.rmSync(bytes, { force: true });

    try {
      await readyToCopy(page, instance);
      if (instance.database.type === "sqlite")
        await runCopy(page, "copy_database");
      if (instance.knowledge_bases.local)
        await runCopy(page, "copy_knowledge_bases");

      await page.goto("/settings/migration");
      const files = page.getByTestId("migration-step-copy_files");
      await files.getByRole("button", { name: "Copy files" }).click();

      // The copy leaves it, says why, and waits for the admin.
      const accept = files.getByRole("checkbox", {
        name: "Move without this file, walk-gone.txt",
      });
      await expect(accept).toBeVisible({ timeout: 300000 });
      await expect(files.getByRole("alert")).toContainText(
        "Some were not copied. Each one below says why.",
      );
      await expect(files).toContainText(
        "Nothing is stored for this name, so there is nothing to copy.",
      );
      // The walk accepted the check's finding about this file on its way here. The step says why it asks again.
      await expect(files).toContainText(
        "Accepting a finding in 'Check this instance' lets the move go on.",
      );

      // Accepted, the step is done with nothing run again. Taken back, it waits again.
      await accept.click();
      await expect(files).toContainText(/Copied: [\d,]+ of [\d,]+/);
      await expect(files.getByRole("alert")).toHaveCount(0);
      await expect(accept).toBeChecked();
      await expect(files).toContainText(/Accepted by .+ on /);
      await accept.click();
      await expect(files.getByRole("alert")).toContainText(
        "Some were not copied.",
      );
      await accept.click();
      await expect(files.getByRole("alert")).toHaveCount(0);
    } finally {
      await startOver(page);
      fs.writeFileSync(bytes, "gone");
    }
  },
);
