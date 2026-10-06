/** One check as `migration-preflight --json` reports it. */
export interface MigrationCheck {
  name: string;
  status: "ok" | "warn" | "fail";
  summary: string;
  problems: string[];
}

export interface AcceptedFinding {
  name: string;
  /** The finding as it was accepted. A different summary later means the acceptance lapsed. */
  summary: string;
  accepted_by: string;
  accepted_at: string;
}

/** The last run of the source checks, as the record keeps it. */
export interface MigrationStep {
  status: "running" | "done" | "failed" | "cancelled";
  started_by: string;
  started_at: string;
  finished_at?: string;
  target_version: string;
  exit_code: number | null;
  report: { ok: boolean; checks: MigrationCheck[] } | null;
  error: string | null;
}

export type MigrationStepId =
  | "check_source"
  | "connect_target"
  | "secret_key"
  | "pause"
  | "backup"
  | "copy_database"
  | "copy_knowledge_bases"
  | "copy_files"
  | "start_target"
  | "check_target";

/** Where the server says a step stands. The page renders it as given. */
export interface MigrationStepState {
  id: MigrationStepId;
  state: "locked" | "current" | "done" | "blocked" | "skipped";
  reason?: string;
}

/** `GET /api/v1/migration`: this instance, the migration record and what it means for each step. */
export interface MigrationState {
  instance: {
    version: string;
    /** `location` is the host, the port and the database name. It holds no user and no password. */
    database: { type: "sqlite" | "postgresql"; location?: string };
    knowledge_bases: { local: boolean };
    files: { storage: "local" | "s3"; local: boolean };
    /** Where this instance's secret key is. The key itself never leaves the server. */
    secret_key?: { source: "file" | "env"; path?: string };
  };
  record: {
    target: { version?: string; set_by?: string; set_at?: string };
    steps: { check_source?: MigrationStep };
    accepted_findings: AcceptedFinding[];
    /** Where the new instance keeps its data. Each part is there only when this instance needs it, and none holds a secret. */
    destinations?: {
      database?: { location: string | null };
      vectors?: { kind: string };
      files?: { bucket: string; prefix: string; endpoint_url?: string | null };
      /** What the last test of each part found. A part that failed is saved too. */
      results?: ProbeResults;
      saved_by: string;
      saved_at: string;
    };
    /** Set once the fingerprint the admin pasted was this instance's. */
    secret_key?: { verified_by?: string; verified_at?: string };
    /** Set while changes to this instance are paused. */
    pause?: { frozen_at: string; frozen_by: string };
  };
  steps: MigrationStepState[];
  blocking_findings: string[];
  acceptable_checks: string[];
}

/** `PUT /api/v1/migration/destinations`: only the parts this instance needs. */
export interface DestinationsRequest {
  database_url?: string;
  vectors?: { kind: "pgvector" };
  files?: {
    bucket: string;
    prefix: string;
    access_key_id: string;
    secret_access_key: string;
    endpoint_url?: string;
    ca_bundle?: string;
  };
}

/** What the server found when it tried one destination. `reason` is in the server's own words, with no secret in it. */
export interface ProbeResult {
  ok: boolean;
  code?: string;
  reason?: string;
}

export type ProbeResults = Partial<
  Record<"database" | "vectors" | "files", ProbeResult>
>;

/** The answer to saving the destinations: the new state and one result for each part sent. */
export interface DestinationsSaved extends MigrationState {
  results: ProbeResults;
}

/** Something still writing to this instance, which the pause waits for. */
export interface MigrationJob {
  id: string;
  flow_name: string | null;
  knowledge_base?: string | null;
  owner: string | null;
  /** `queued`, `in_progress`, `suspended`, or `ingesting` for a knowledge base. */
  state: string;
  started_at: string;
  /** The request that cancels the job through its own route, when the admin may send it. */
  cancel: { method: string; url: string; body: unknown } | null;
}

/** The `detail` of a request the server refused. */
export interface MigrationError {
  code: string;
  source_version?: string;
  path?: string;
  /** With `jobs_active`: what the pause waits for. */
  jobs?: MigrationJob[];
  /** With `jobs_active`: each trigger listener process that is still running. */
  listeners?: { holder: string }[];
}

/** One line of the `POST /api/v1/migration/checks` stream. */
export type MigrationCheckEvent =
  | { event: "check"; check: MigrationCheck }
  | { event: "report"; ok: boolean; checks: MigrationCheck[] }
  | { event: "error"; message: string };
