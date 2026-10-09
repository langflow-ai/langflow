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
    database: { type: "sqlite" | "postgresql" };
    knowledge_bases: { local: boolean };
    files: { storage: "local" | "s3"; local: boolean };
  };
  record: {
    target: { version?: string; set_by?: string; set_at?: string };
    steps: { check_source?: MigrationStep };
    accepted_findings: AcceptedFinding[];
  };
  steps: MigrationStepState[];
  blocking_findings: string[];
  acceptable_checks: string[];
}

/** The `detail` of a request the server refused. */
export interface MigrationError {
  code: string;
  source_version?: string;
  path?: string;
}

/** One line of the `POST /api/v1/migration/checks` stream. */
export type MigrationCheckEvent =
  | { event: "check"; check: MigrationCheck }
  | { event: "report"; ok: boolean; checks: MigrationCheck[] }
  | { event: "error"; message: string };
