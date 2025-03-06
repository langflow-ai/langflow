export interface Subscription {
  id: string;
  flow_id: string;
  event_type: string;
  category: string | null;
  state: string | null;
  created_at?: string;
  updated_at?: string;
}
