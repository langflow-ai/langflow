import fs from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";

/**
 * Where the walks through Settings > Migration send this instance's data. The page tests each
 * destination for real, so the walks run only where these name an empty PostgreSQL database and
 * an S3 bucket. They share one migration record, so run them one at a time, against a server
 * no other spec is using.
 */
export const DESTINATION = {
  databaseUrl: process.env.MIGRATION_E2E_DATABASE_URL ?? "",
  bucket: process.env.MIGRATION_E2E_S3_BUCKET ?? "",
  endpointUrl: process.env.MIGRATION_E2E_S3_ENDPOINT ?? "",
  accessKeyId: process.env.MIGRATION_E2E_S3_ACCESS_KEY_ID ?? "any",
  secretAccessKey: process.env.MIGRATION_E2E_S3_SECRET_ACCESS_KEY ?? "any", // pragma: allowlist secret
};

export const NO_DESTINATION =
  !DESTINATION.databaseUrl || !DESTINATION.bucket
    ? "Set MIGRATION_E2E_DATABASE_URL and MIGRATION_E2E_S3_BUCKET (and MIGRATION_E2E_S3_ENDPOINT unless the bucket is on Amazon S3)."
    : "";

/**
 * Starts the move over and answers with this instance's facts. The migration record is a file next
 * to the instance's data, and a walk runs on the machine the server runs on, so it removes the file.
 * That also ends a pause an earlier walk left on.
 */
export async function startOver(page: Page) {
  const read = async () =>
    (await (await page.request.get("/api/v1/migration")).json()).instance;
  const { files } = await read();
  fs.rmSync(path.join(files.folder, "migrations", "migration.json"), {
    force: true,
  });
  return read();
}
