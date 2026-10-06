import type {
  AcceptedFinding,
  CopyEvent,
  CopyStepId,
  DestinationsRequest,
  MigrationCheck,
  MigrationState,
  MigrationStepId,
} from "@/controllers/API/queries/migration";

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

/** The copy steps this page can run. Each slug names its copy under `settings.migration.*`. */
export const COPIES: Partial<Record<CopyStepId, { slug: string }>> = {
  copy_database: { slug: "copyDb" },
};

export const isCopy = (id: MigrationStepId): id is CopyStepId => id in COPIES;

/**
 * The page's line, under `settings.migration.*`, for each reason a copy does not start or does not count.
 * Any other code reads as a failure, with the command's own words under it.
 */
export const COPY_CODES: Record<string, string> = {
  secrets_missing: "error.enterAgain", // pragma: allowlist secret
  run_active: "error.runningElsewhere",
  cancelled: "error.interrupted",
  interrupted: "error.interrupted",
  crashed: "error.crashed",
  destination_changed: "error.destinationChanged",
  target_unreachable: "error.targetUnreachable",
  target_not_empty: "error.dbTargetNotEmpty",
  // The destination holds an earlier copy, and this instance lost a row since. Only a new, empty one takes a copy.
  count_mismatch: "error.dbCountMismatch",
  orphans_no_rule: "error.orphansNoRule",
  value_rejected: "error.valueRejected",
};

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
    `${COPIES[step]?.slug}.progress`,
    { done: count(event.done), total: count(event.total) },
  ];
}
