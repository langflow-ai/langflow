export type FlowScheduleType = {
  id: string;
  flow_id: string;
  user_id: string;
  name: string | null;
  is_active: boolean;
  cron_expression: string;
  timezone: string;
  days_of_week: number[] | null;
  times_of_day: string[] | null;
  repeat_frequency: string | null;
  created_at: string;
  updated_at: string;
  last_run_at: string | null;
  next_run_at: string | null;
  last_run_status: string | null;
  last_run_error: string | null;
};

export type FlowScheduleCreateType = {
  flow_id: string;
  name?: string | null;
  is_active?: boolean;
  cron_expression: string;
  timezone: string;
  days_of_week?: number[] | null;
  times_of_day?: string[] | null;
  repeat_frequency?: string | null;
};

export type FlowScheduleUpdateType = {
  name?: string | null;
  is_active?: boolean;
  cron_expression?: string;
  timezone?: string;
  days_of_week?: number[] | null;
  times_of_day?: string[] | null;
  repeat_frequency?: string | null;
};
