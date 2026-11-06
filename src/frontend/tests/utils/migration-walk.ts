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
 * That also ends a pause an earlier walk left on. A copy an earlier walk left running is stopped first,
 * because the server runs one at a time.
 */
export async function startOver(page: Page) {
  const read = async () => (await page.request.get("/api/v1/migration")).json();
  const { instance, record } = await read();
  for (const [step, run] of Object.entries<{ run_id?: string }>(record.steps)) {
    if (run.run_id)
      await page.request.delete(
        `/api/v1/migration/steps/${step}/runs/${run.run_id}`,
      );
  }
  fs.rmSync(path.join(instance.files.folder, "migrations", "migration.json"), {
    force: true,
  });
  return (await read()).instance;
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
  // What the check found that an admin may accept is accepted, as on the page.
  const { blocking_findings } = await (
    await page.request.get("/api/v1/migration")
  ).json();
  for (const name of blocking_findings)
    await page.request.post("/api/v1/migration/accepted-findings", {
      data: { name },
    });
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

/** Does every step before the copies through the API: the ones before the pause, the pause with its second check, and the backup. */
export async function readyToCopy(
  page: Page,
  instance: Awaited<ReturnType<typeof startOver>>,
) {
  await prepare(page, instance);
  await page.request.post("/api/v1/migration/pause");
  const check = await page.request.post("/api/v1/migration/checks", {
    data: { target_version: instance.version },
    timeout: 120000,
  });
  await check.body();
  // On SQLite the backup of the database is the copy the server hands out.
  if (instance.database.type === "sqlite")
    await page.request.post("/api/v1/migration/backup/database");
  await page.request.post("/api/v1/migration/steps/backup/confirm", {
    data: { location: "a browser walk" },
  });
}

/** Makes a copy through the API, or a test run of one, and waits for its end. */
export async function runCopy(page: Page, step: string, dryRun = false) {
  const started = await page.request.post(
    `/api/v1/migration/steps/${step}/runs`,
    { data: { dry_run: dryRun } },
  );
  const { run_id } = await started.json();
  // The events answer as a stream that ends when the run does.
  const events = await page.request.get(
    `/api/v1/migration/steps/${step}/runs/${run_id}/events`,
    { timeout: 300000 },
  );
  await events.body();
}
