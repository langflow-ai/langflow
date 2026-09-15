import { readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

function zipFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return zipFiles(path);
    return entry.isFile() && entry.name.endsWith(".zip") ? [path] : [];
  });
}

export function resolveBlobReports(directory, expectedReports) {
  if (!Number.isSafeInteger(expectedReports) || expectedReports < 1) {
    throw new Error("Expected report count must be a positive integer.");
  }
  const root = resolve(directory);
  const reports = zipFiles(root);
  const flatReports = reports.filter((path) => dirname(path) === root);
  // download-artifact v8 flattens a sole match even with merge-multiple=false.
  // Its artifact name (and attempt number) is unavailable in this layout.
  if (flatReports.length) {
    if (expectedReports !== 1 || reports.length !== 1) {
      throw new Error(
        "A flat download must contain exactly one expected report.",
      );
    }
    return [{ shard: 1, attempt: null, path: flatReports[0] }];
  }

  const selected = new Map();
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const match = /^blob-report-.*-(\d+)-of-(\d+)-attempt-(\d+)$/.exec(
      entry.name,
    );
    const artifacts = zipFiles(join(root, entry.name));
    if (!match) {
      if (artifacts.length) {
        throw new Error(`Unrecognized report artifact: ${entry.name}`);
      }
      continue;
    }
    const [, shardText, totalText, attemptText] = match;
    const [shard, total, attempt] = [shardText, totalText, attemptText].map(
      Number,
    );
    if (
      ![shard, total, attempt].every(Number.isSafeInteger) ||
      total !== expectedReports ||
      shard < 1 ||
      shard > total ||
      attempt < 1
    ) {
      throw new Error(`Invalid report artifact: ${entry.name}`);
    }
    if (artifacts.length !== 1) {
      throw new Error(`Expected one blob zip in ${entry.name}.`);
    }
    const previous = selected.get(shard);
    if (previous?.attempt === attempt) {
      throw new Error(
        `Ambiguous reports for shard ${shard}, attempt ${attempt}.`,
      );
    }
    if (!previous || attempt > previous.attempt) {
      selected.set(shard, { shard, attempt, path: artifacts[0] });
    }
  }
  const missing = Array.from(
    { length: expectedReports },
    (_, index) => index + 1,
  ).filter((shard) => !selected.has(shard));
  if (missing.length) {
    throw new Error(`Missing blob reports for shards: ${missing.join(", ")}.`);
  }
  return [...selected.values()].sort((left, right) => left.shard - right.shard);
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const reports = resolveBlobReports(process.argv[2], Number(process.argv[3]));
  for (const { shard, attempt, path } of reports) {
    process.stdout.write(`${shard}\t${attempt ?? "single"}\t${path}\n`);
  }
}
