import { createHash } from "node:crypto";
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

/** What the admin reads where the new instance's key is set: the first 12 characters of the key's SHA-256. */
export const fingerprint = (keyFile: string) =>
  createHash("sha256")
    .update(fs.readFileSync(keyFile))
    .digest("hex")
    .slice(0, 12);

/** Does the steps before the pause through the API, with the answers the first walk gives on the page. */
export async function prepare(
  page: Page,
  instance: Awaited<ReturnType<typeof startOver>>,
) {
  // The check answers as a stream, and reading it to the end waits for the last result.
  const check = await page.request.post("/api/v1/migration/checks", {
    data: { target_version: instance.version },
    timeout: 120000,
  });
  await check.body();
  await page.request.put("/api/v1/migration/destinations", {
    data: {
      ...(instance.database.type === "sqlite" && {
        database_url: DESTINATION.databaseUrl,
      }),
      ...(instance.knowledge_bases.local && { vectors: { kind: "pgvector" } }),
      ...(instance.files.local && {
        files: {
          bucket: DESTINATION.bucket,
          prefix: "files",
          access_key_id: DESTINATION.accessKeyId,
          secret_access_key: DESTINATION.secretAccessKey, // pragma: allowlist secret
          endpoint_url: DESTINATION.endpointUrl || undefined,
        },
      }),
    },
  });
  await page.request.post("/api/v1/migration/secret-key/verify", {
    data: { fingerprint: fingerprint(instance.secret_key.path) },
  });
}
