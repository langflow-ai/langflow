// Domain types mirroring the backend Pydantic schemas in
// langflow.services.database.models.triggers.model.

export type TriggerType = "cron";

export type JobStatus =
  | "queued"
  | "in_progress"
  | "completed"
  | "failed"
  | "cancelled"
  | "timed_out";

export interface Trigger {
  id: string;
  flow_id: string;
  user_id: string;
  name: string;
  trigger_type: TriggerType;
  cron_expression: string | null;
  timezone: string;
  payload: Record<string, unknown> | null;
  max_attempts: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TriggerCreate {
  flow_id: string;
  name: string;
  cron_expression: string;
  timezone?: string;
  payload?: Record<string, unknown> | null;
  max_attempts?: number;
  is_active?: boolean;
  trigger_type?: TriggerType;
}

export type TriggerUpdate = Partial<
  Pick<
    Trigger,
    "name" | "cron_expression" | "timezone" | "payload" | "max_attempts" | "is_active"
  >
>;

export interface TriggerJob {
  id: string;
  trigger_id: string;
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
