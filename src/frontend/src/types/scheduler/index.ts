export type SchedulerType = {
  id: string;
  name: string;
  description: string | null;
  flow_id: string;
  cron_expression: string | null;
  interval_seconds: number | null;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
};

export type SchedulerCreateType = {
  name: string;
  description?: string;
  flow_id: string;
  cron_expression?: string;
  interval_seconds?: number;
  enabled?: boolean;
};

export type SchedulerUpdateType = {
  name?: string;
  description?: string;
  cron_expression?: string;
  interval_seconds?: number;
  enabled?: boolean;
}; 