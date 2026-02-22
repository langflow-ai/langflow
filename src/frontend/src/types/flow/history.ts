export type FlowHistoryEntry = {
  id: string;
  flow_id: string;
  user_id: string;
  state: "DRAFT" | "PUBLISHED" | "ARCHIVED";
  version_number: number;
  version_tag: string;
  description: string | null;
  created_at: string;
};

export type FlowHistoryEntryFull = FlowHistoryEntry & {
  data: Record<string, any> | null;
};

export type FlowHistoryCreate = {
  description?: string | null;
};
