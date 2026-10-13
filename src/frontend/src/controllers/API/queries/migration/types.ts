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

/** The steps that copy this instance's data. Each one runs a command of its own on the server. */
export type CopyStepId =
  | "copy_database"
  | "copy_knowledge_bases"
  | "copy_files";

/** Rows of one table that point at a row of another that is gone. */
export interface OrphanRows {
  table: string;
  column: string;
  parent: string;
  /** The foreign key's ON DELETE rule: `CASCADE` rows are left out, `SET NULL` rows are copied with the key cleared. */
  ondelete: string;
  rows: number;
}

/**
 * A decision the server offers about a copy, to send back as it came. With a `subject` it accepts that one
 * item at once. With none it is an option for the whole step, which the next copy takes.
 */
export interface CopyDecision {
  kind: string;
  subject: string | null;
  /** The run whose report the item is in. An acceptance is for that report only. An option has none. */
  run_id?: string | null;
  /** Who made it and when, while the server holds it as made: an option for the step, an acceptance for the run on record. */
  made?: { by: string; at: string } | null;
}

/** A knowledge base or a file that a copy did not make, as the command reported it. */
export interface CopyItem {
  /** The name a decision about this item uses: a knowledge base's id, or a file's owner and name. */
  subject: string;
  kb_name?: string;
  file_name?: string;
  owner: string;
  code: string | null;
  /** The command's own words for what happened. */
  reason: string | null;
  /** The decision that answers this item's code, when the server has one. */
  decision?: CopyDecision | null;
}

/** The latest run of a copy step, as the record keeps it. */
export interface MigrationCopyRun {
  run_id: string;
  status: "running" | "done" | "failed" | "cancelled" | "interrupted";
  /** A test run says what a copy would do and never completes its step. */
  dry_run: boolean;
  started_by: string;
  started_at: string;
  finished_at: string | null;
  /** The command's last word on a run that ended. */
  report: {
    ok: boolean;
    tables_copied?: number;
    rows_copied?: number;
    problems?: { code: string; message: string }[];
    /** The database copy: the rows it left out on the admin's word. */
    orphans?: OrphanRows[];
    /** Knowledge bases and files: how many ended in each status, a test run's `would_` ones included. */
    counts?: Record<string, number>;
    /** The first hundred that failed. `counts.failed` says how many did. */
    attention?: CopyItem[];
  } | null;
  /** Set when the run did not end done: the command's own code and message, or `crashed`, `cancelled` or `interrupted`. */
  error: { code: string; message?: string } | null;
  /** What the command asked before it would copy: the rows that point at nothing, and the decision that leaves them out. */
  decision_needed?: {
    code: string;
    details?: { orphans?: OrphanRows[] };
    decision?: CopyDecision | null;
  } | null;
}

/** One line of a run's event stream. The server numbers each, so a page can ask for what came after one. */
export interface CopyEvent {
  event: "progress" | "item" | "report" | "error" | "decision_needed" | "end";
  seq: number;
  /** On `progress`: `checking`, `preparing_target` or `copying`. A line with none is copying. */
  phase?: string;
  done?: number;
  total?: number | null;
  /** The file copy: how much it has copied so far. */
  bytes?: number;
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
  | "check_target"
  | "start_target";

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
    knowledge_bases: { local: boolean; folder?: string | null };
    files: { storage: "local" | "s3"; local: boolean; folder?: string };
    /** Where this instance's secret key is. The key itself never leaves the server. */
    secret_key?: { source: "file" | "env"; path?: string };
  };
  record: {
    target: { version?: string; set_by?: string; set_at?: string };
    steps: {
      check_source?: MigrationStep;
      /** Set once the admin said that the new instance runs on the copied data, which ends the move. */
      start_target?: { confirmed_by?: string; confirmed_at?: string };
      check_target?: MigrationTargetCheck;
    } & Partial<Record<CopyStepId, MigrationCopyRun>>;
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
    /**
     * Set while a request for a pause still waits for changes to end. Changes are refused already.
     * It stays when the server stopped during that wait.
     */
    pausing?: { frozen_at: string; frozen_by: string };
    backup?: {
      location?: string;
      database_downloaded_at?: string;
      confirmed_by?: string;
      confirmed_at?: string;
    };
  };
  steps: MigrationStepState[];
  blocking_findings: string[];
  acceptable_checks: string[];
  /** What "Start the new instance" shows once the admin has reached it. */
  start?: { settings: MigrationSetting[] };
}

/** One check as it came out on the copied data, beside this instance's last result for the same check. */
export interface MigrationComparedCheck {
  /** The check's name for the copy, which is this instance's without "source: ". */
  name: string;
  /** `problems` are the examples the check printed, often none. */
  there: { status: string; summary: string; problems?: string[] };
  here: { status: string; summary: string } | null;
  same: boolean;
  /** The admin accepted this check's finding on this instance in the first step. */
  accepted: boolean;
}

/**
 * What the admin says before changes go back on once the new instance has started: that it is stopped, and,
 * where it shared this instance's database, that the database is restored from the backup.
 */
export interface MigrationWayBack {
  target_stopped: boolean;
  database_restored?: boolean;
}

/** The run that checks the copy, and the admin's word about what it found different. */
export interface MigrationTargetCheck {
  run_id?: string;
  status?: MigrationCopyRun["status"];
  started_by?: string;
  started_at?: string;
  finished_at?: string | null;
  /** Set when the run did not end done, as for a copy. */
  error?: { code: string; message?: string } | null;
  /** `ok` when every check came out the same on both sides. */
  report?: { ok: boolean; checks: MigrationComparedCheck[] } | null;
  confirmed_by?: string;
  confirmed_at?: string;
  /** The checks that differed when the admin said that each difference was expected, and went on. */
  accepted_differences?: string[];
}

/**
 * One setting the new instance has to start with, in the order to show it.
 * `fill` marks a value the server never sends, a password or a key: `value` then holds a placeholder for the admin to replace.
 */
export interface MigrationSetting {
  name: string;
  value: string;
  fill: boolean;
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

/** A change this worker process let in before the pause that has not ended. Each kind fills the parts it has. */
export interface MigrationChange {
  kind: "request" | "websocket" | "task" | "loop";
  /** A request's method, such as `POST`. */
  method: string | null;
  /** A request's or a websocket's path, with no query string. */
  path: string | null;
  /** A task's name, such as `webhook_run`, or a loop's, such as `trigger_dispatcher`. */
  name: string | null;
  /** When it started, in UTC. */
  since: string;
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
  /** With `jobs_active` and `requests_active`: the changes that have not ended. */
  changes?: MigrationChange[];
  /** With `requests_active`: another worker process still handles a change that this one cannot name. */
  elsewhere?: boolean;
}

/** One line of the `POST /api/v1/migration/checks` stream. */
export type MigrationCheckEvent =
  | { event: "check"; check: MigrationCheck }
  | { event: "report"; ok: boolean; checks: MigrationCheck[] }
  | { event: "error"; message: string };
