import type {
  AcceptedFinding,
  CopyEvent,
  CopyStepId,
  DestinationsRequest,
  MigrationCheck,
  MigrationState,
  MigrationStepId,
} from "@/controllers/API/queries/migration";
import { formatFileSize } from "@/utils/stringManipulation";

/** The steps in page order, by part. Each slug names its copy under `settings.migration.step.*`. */
export const PARTS: {
  slug: "prepare" | "move" | "switch";
  steps: { id: MigrationStepId; slug: string }[];
}[] = [
  {
    slug: "prepare",
    steps: [
      { id: "check_source", slug: "check" },
      { id: "connect_target", slug: "destinations" },
      { id: "secret_key", slug: "secretKey" },
    ],
  },
  {
    slug: "move",
    steps: [
      { id: "pause", slug: "pause" },
      { id: "backup", slug: "backup" },
      { id: "copy_database", slug: "copyDatabase" },
      { id: "copy_knowledge_bases", slug: "copyKnowledgeBases" },
      { id: "copy_files", slug: "copyFiles" },
    ],
  },
  {
    slug: "switch",
    steps: [
      { id: "start_target", slug: "start" },
      { id: "check_target", slug: "checkTarget" },
    ],
  },
];

export const STEP_SLUGS = Object.fromEntries(
  PARTS.flatMap((part) => part.steps).map((step) => [step.id, step.slug]),
) as Record<MigrationStepId, string>;

/**
 * The page's copy for each check the server sends, by the name migration-preflight gives it.
 * `accept` means the check has an accept label; the server decides what can be accepted.
 * `handledIn` is the step where a warning is dealt with.
 */
export const CHECKS: Record<
  string,
  { slug: string; accept?: boolean; handledIn?: MigrationStepId }
> = {
  version: { slug: "version" },
  "source: schema": { slug: "schema" },
  "default superuser": {
    slug: "defaultSuperuser",
    accept: true,
    handledIn: "start_target",
  },
  "embedding models": {
    slug: "embeddingModels",
    handledIn: "copy_knowledge_bases",
  },
  "role assignments": { slug: "roleAssignments", handledIn: "start_target" },
  "source: credentials": { slug: "credentials" },
  "source: files": { slug: "files", accept: true },
  "source: knowledge base storage": { slug: "knowledgeBaseStorage" },
  "source: knowledge bases": { slug: "knowledgeBases", accept: true },
  "source: vector counts": { slug: "vectorCounts", accept: true },
  "source: memory bases": { slug: "memoryBases" },
  "source: authorization": { slug: "authorization" },
};

export const CHECK_TOTAL = Object.keys(CHECKS).length;

/** Sorts checks into the page's groups, keeping run order inside each. */
export function groupChecks(checks: MigrationCheck[], acceptable: string[]) {
  // When the schema check fails, the other checks couldn't read the database.
  const schema = checks.find(
    (check) => check.name === "source: schema" && check.status === "fail",
  );
  const shown = schema ? [schema] : checks;
  const failing = shown.filter((check) => check.status === "fail");
  return {
    fix: failing.filter((check) => !acceptable.includes(check.name)),
    decide: failing.filter((check) => acceptable.includes(check.name)),
    read: shown.filter((check) => check.status === "warn"),
    passed: shown.filter((check) => check.status === "ok"),
    notRun: Boolean(schema),
  };
}

/** The acceptance of a finding. It lapses when the finding changed after it was accepted. */
export function acceptanceOf(
  check: MigrationCheck,
  accepted: AcceptedFinding[],
) {
  const finding = accepted.find((item) => item.name === check.name);
  return finding && { finding, lapsed: finding.summary !== check.summary };
}

export const formatTime = (value: string | undefined, language: string) =>
  value ? new Date(value).toLocaleString(language) : "";

/** The page's line, under `settings.migration.*`, for each reason the server refuses a destination. */
export const PROBES: Record<string, string> = {
  db_unreachable: "probe.unreachable",
  db_not_empty: "probe.dbNotEmpty",
  no_create: "probe.noCreate",
  pgvector_missing: "probe.pgvector",
  pgvector_package_missing: "probe.pgvectorPackage",
  pgvector_env_missing: "probe.pgvectorEnv",
  bucket_missing: "probe.bucketMissing",
  bucket_unreachable: "probe.bucketUnreachable",
  bucket_denied: "probe.denied",
  secrets_missing: "dest.enterAgain", // pragma: allowlist secret
};

/** What "Where your data goes" sends: only the parts this instance keeps on its own server. Fields are named as the API names them. */
export function destinationsRequest(
  instance: MigrationState["instance"],
  form: FormData,
): DestinationsRequest {
  const field = (name: string) => String(form.get(name) ?? "").trim();
  return {
    ...(instance.database.type === "sqlite" && {
      database_url: field("database_url"),
    }),
    // The only store the copy can write to for now, so the admin isn't asked.
    ...(instance.knowledge_bases.local && { vectors: { kind: "pgvector" } }),
    ...(instance.files.local && {
      files: {
        bucket: field("bucket"),
        prefix: field("prefix"),
        access_key_id: field("access_key_id"),
        secret_access_key: field("secret_access_key"), // pragma: allowlist secret
        ...(field("endpoint_url") && { endpoint_url: field("endpoint_url") }),
        ...(field("ca_bundle") && { ca_bundle: field("ca_bundle") }),
      },
    }),
  };
}

/** The page's words, under `settings.migration.job.*`, for each state of something the pause waits for. */
export const JOB_STATES: Record<string, string> = {
  queued: "queued",
  in_progress: "running",
  suspended: "waiting",
  ingesting: "ingesting",
};

/**
 * An example backup command for this instance's PostgreSQL database, with no user and no password.
 * The server gives the location as `host:port/database`, or `host/database` on the default port.
 */
export function pgDumpCommand(location: string) {
  const slash = location.indexOf("/");
  const address = location.slice(0, slash);
  const parts = /^(\[[^\]]+\]|[^:]+)(?::(\d+))?$/.exec(address);
  const host = parts ? parts[1].replace(/^\[|\]$/g, "") : address;
  const port = parts?.[2];
  return `pg_dump -h ${shellArgument(host)}${port ? ` -p ${port}` : ""} -d ${shellArgument(location.slice(slash + 1))} -F c -f langflow-backup.dump`;
}

function shellArgument(value: string) {
  return /^[A-Za-z0-9_.:/-]+$/.test(value)
    ? value
    : `'${value.replaceAll("'", "'\\''")}'`;
}

/**
 * The copy steps, with the keys of their own lines under `settings.migration.*`: the progress line is
 * `<slug>.progress`. `testRun` is set where the server can say what a copy would do without making it.
 */
export const COPIES: Record<
  CopyStepId,
  { slug: string; body: string; stopBody: string; testRun?: boolean }
> = {
  copy_database: {
    slug: "copyDb",
    body: "copyDb.body",
    stopBody: "copyDb.stopBody",
  },
  copy_knowledge_bases: {
    slug: "kb",
    body: "copy.body",
    stopBody: "copy.stopBody",
    testRun: true,
  },
  copy_files: {
    slug: "files",
    body: "copy.body",
    stopBody: "copy.stopBody",
    testRun: true,
  },
};

export const isCopy = (id: MigrationStepId): id is CopyStepId => id in COPIES;

/**
 * The page's line, under `settings.migration.*`, for each reason a copy does not start or does not count.
 * Any other code reads as a failure, with the command's own words under it.
 */
export const COPY_CODES: Record<string, string> = {
  secrets_missing: "error.enterAgain", // pragma: allowlist secret
  run_active: "error.runningElsewhere",
  // A step above opened again after the page last read the state. The page then stops offering the start.
  locked: "notStarted",
  cancelled: "error.interrupted",
  interrupted: "error.interrupted",
  crashed: "error.crashed",
  destination_changed: "error.destinationChanged",
  // The knowledge bases test of "Where your data goes" refuses for the same reason. Its line follows a note
  // that says where they go, and this one stands alone.
  pgvector_env_missing: "kb.postgresEnv",
  target_unreachable: "error.targetUnreachable",
  target_not_empty: "error.dbTargetNotEmpty",
  // The destination holds an earlier copy, and this instance lost a row since. Only a new, empty one takes a copy.
  count_mismatch: "error.dbCountMismatch",
  orphans_droppable: "copyDb.orphans.title",
  orphans_no_rule: "error.orphansNoRule",
  value_rejected: "error.valueRejected",
  bucket_error: "error.bucket",
};

/**
 * The page's line, under `settings.migration.*`, for each reason one knowledge base or one file is not copied.
 * Any other code reads as not copied, with the command's own words under it.
 */
export const ITEM_CODES: Record<string, string> = {
  kb_ingesting: "error.kbIngesting",
  kb_short: "error.kbShort",
  kb_target_more: "error.kbTargetMore",
  // Each of these three is over once the copy is made again.
  kb_changed: "error.kbChanged",
  kb_routing_changed: "error.kbChanged",
  kb_deleted: "error.kbChanged",
  kb_backend_missing: "error.kbBackend",
  kb_metric_change: "kb.ranking.body",
  kb_upgrade_pending: "error.kbUpgrade",
  file_conflict: "files.conflict",
  bad_name: "files.badName",
  no_source_bytes: "files.noFile",
  attachment_unmatched: "files.noFile",
  bucket_error: "error.bucket",
};

/**
 * What a copy of knowledge bases or of files counted, whichever it was and whether it was a test run:
 * copied (or to copy), there already, and not copied.
 */
export function copyCounts(counts: Record<string, number> = {}) {
  const sum = (...statuses: string[]) =>
    statuses.reduce((total, status) => total + (counts[status] ?? 0), 0);
  return {
    copied: sum("relocated", "copied", "would_relocate", "would_copy"),
    skipped: sum("skipped"),
    failed: sum("failed"),
  };
}

/** How far a run has got: the key of its line under `settings.migration.*`, and the counts that fill it. */
export function copyProgress(
  step: CopyStepId,
  event: CopyEvent,
  language: string,
): [string, Record<string, string>] {
  if (event.phase === "checking") return ["copy.checking", {}];
  if (event.phase === "preparing_target") return ["copy.preparing", {}];
  const count = (value?: number | null) =>
    (value ?? 0).toLocaleString(language);
  return [
    `${COPIES[step].slug}.progress`,
    {
      done: count(event.done),
      total: count(event.total),
      ...(event.bytes !== undefined && { bytes: formatFileSize(event.bytes) }),
    },
  ];
}

/**
 * The label of each decision the server can offer about a copy, as a key under `settings.migration.*`.
 * Which item gets which decision is the server's to say.
 */
export const DECISIONS: Record<string, string> = {
  drop_orphans: "copyDb.orphans.accept",
  accept_ranking_change: "kb.ranking.accept",
  leave_behind: "kb.leaveBehind",
  keep_bucket_file: "files.keepBucket",
  accept_missing_attachment: "files.acceptMissing",
};
