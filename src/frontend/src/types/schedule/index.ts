export type FlowScheduleType = {
  id: string;
  flow_id: string;
  user_id: string;
  is_active: boolean;
  schedule_type: string;
  minute: string;
  hour: string;
  day_of_week: string;
  day_of_month: string;
  month: string;
  timezone: string;
  start_at?: string | null;
  last_run_at?: string;
  last_run_status?: string;
  created_at: string;
  updated_at: string;
};

export type FlowScheduleCreateType = {
  flow_id: string;
  is_active?: boolean;
  schedule_type?: string;
  minute?: string;
  hour?: string;
  day_of_week?: string;
  day_of_month?: string;
  month?: string;
  timezone?: string;
  start_at?: string;
};

export type FlowScheduleUpdateType = {
  is_active?: boolean;
  schedule_type?: string;
  minute?: string;
  hour?: string;
  day_of_week?: string;
  day_of_month?: string;
  month?: string;
  timezone?: string;
  start_at?: string;
};
