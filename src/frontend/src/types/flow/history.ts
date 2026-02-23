export type FlowHistoryEntry = {
  id: string;
  flow_id: string;
  user_id: string;
  version_number: number;
  version_tag: string;
  description: string | null;
  created_at: string;
};

export type FlowHistoryEntryWithData = FlowHistoryEntry & {
  data: Record<string, any> | null;
};

export type FlowHistoryCreate = {
  description?: string | null;
};

export type FlowHistoryListResponse = {
  entries: FlowHistoryEntry[];
  max_entries: number;
};
