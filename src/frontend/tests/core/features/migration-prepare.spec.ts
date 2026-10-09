import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  DESTINATION,
  NO_DESTINATION,
  startOver,
} from "../../utils/migration-walk";

test(
  "an admin says where this instance's data goes",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    test.skip(Boolean(NO_DESTINATION), NO_DESTINATION);
    await awaitBootstrapTest(page, { skipModal: true });
    let instance = await startOver(page);
    if (!instance.files.local) {
      // A file on this server, so the move has files to find a place for.
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

    try {
      await page.goto("/settings/migration");
      const version = page.getByTestId("migration-target-version");
      await version.fill((await version.getAttribute("placeholder")) ?? "");
      await page.getByTestId("migration-run-checks").click();
      await expect(page.getByTestId("migration-checks-summary")).toContainText(
        "Nothing stops the move.",
        { timeout: 120000 },
      );

      // The check passed, so the next step opens and takes the focus.
      const destinations = page.getByTestId("migration-step-connect_target");
      await expect(
        destinations.getByRole("heading", { name: "Where your data goes" }),
      ).toBeFocused();
      await destinations
        .getByLabel("Connection address")
        .fill(DESTINATION.databaseUrl);
      await destinations
        .getByLabel("Bucket", { exact: true })
        .fill(`${DESTINATION.bucket}-not-there`);
      await destinations
        .getByLabel("Access key ID")
        .fill(DESTINATION.accessKeyId);
      await destinations
        .getByLabel("Secret access key")
        .fill(DESTINATION.secretAccessKey);
      await destinations.getByLabel("Endpoint").fill(DESTINATION.endpointUrl);
      await destinations.getByRole("button", { name: "Test and save" }).click();

      // Each destination is tested for real, and a refused one says why next to its own fields.
      await expect(destinations.getByText("Ready.")).toBeVisible({
        timeout: 60000,
      });
      const refusal = destinations.getByRole("alert");
      await expect(refusal).toContainText("Can't find this bucket.");
      // The server's own words for what it ran into come with this answer.
      await expect(refusal.locator('[lang="en"]')).not.toBeEmpty();
      await expect(
        destinations.getByLabel("Bucket", { exact: true }),
      ).toHaveAttribute("aria-invalid", "true");

      await destinations
        .getByLabel("Bucket", { exact: true })
        .fill(DESTINATION.bucket);
      await destinations.getByRole("button", { name: "Test and save" }).click();

      // Saved: the row says where the data goes, and no password or key is left on the page.
      const { host, pathname } = new URL(DESTINATION.databaseUrl);
      await expect(destinations).toContainText(
        `Database: ${host}${pathname} · Files: ${DESTINATION.bucket}`,
        { timeout: 60000 },
      );
      await expect(destinations.locator("input")).toHaveCount(0);

      // The step can ask again, and it never got the passwords back.
      await destinations
        .getByRole("button", { name: "Change or enter again" })
        .click();
      await expect(
        destinations.getByLabel("Bucket", { exact: true }),
      ).toHaveValue(DESTINATION.bucket);
      await expect(destinations.getByLabel("Connection address")).toHaveValue(
        "",
      );
      await expect(destinations.getByLabel("Secret access key")).toHaveValue(
        "",
      );
      await expect(destinations.getByText("Ready.")).toHaveCount(0);

      // Entered again and saved, the step closes as it did the first time.
      await destinations
        .getByLabel("Connection address")
        .fill(DESTINATION.databaseUrl);
      await destinations
        .getByLabel("Access key ID")
        .fill(DESTINATION.accessKeyId);
      await destinations
        .getByLabel("Secret access key")
        .fill(DESTINATION.secretAccessKey);
      await destinations.getByRole("button", { name: "Test and save" }).click();
      await expect(destinations.locator("input")).toHaveCount(0, {
        timeout: 60000,
      });
    } finally {
      // The record this walk wrote would put the next one, or another spec, past the first steps.
      await startOver(page);
    }
  },
);
