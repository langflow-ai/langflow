// Shapes the trigger management page consumes.
//
// Mirrors the backend serialisation in api/v1/triggers.py — the
// schedule itself lives inside flow.data as a CronTrigger node, so
// the page has no "trigger entity" to persist, only the aggregator
// projection.

export type JobStatus =
  | "queued"
  | "in_progress"
  | "completed"
  | "failed"
  | "cancelled"
  | "timed_out";

/** One CronTrigger component instance, joined with queue stats. */
export interface TriggerInstance {
  flow_id: string;
  flow_name: string;
  component_id: string;
  cron_expression: string;
  timezone: string;
  max_attempts: number;
  next_fire_at: string | null;
  last_finished_status: JobStatus | null;
  last_finished_at: string | null;
}

/** One row in the trigger_job history list. */
export interface TriggerJob {
  id: string;
  flow_id: string;
  component_id: string;
  status: JobStatus;
  scheduled_at: string;
  started_at: string | null;
  finished_at: string | null;
  attempt: number;
  max_attempts: number;
  error: string | null;
  run_job_id: string | null;
  created_at: string;
}

/** Response shape of the bulk-delete endpoint. */
export interface BulkDeleteSummary {
  flows_updated: number;
  components_removed: number;
}
