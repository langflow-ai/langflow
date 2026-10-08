import type {
  AcceptedFinding,
  MigrationCheck,
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
