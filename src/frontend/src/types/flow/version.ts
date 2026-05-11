export type FlowVersionEntry = {
  id: string;
  flow_id: string;
  user_id: string;
  version_number: number;
  version_tag: string;
  description: string | null;
  created_at: string;
};

export type FlowVersionEntryWithData = FlowVersionEntry & {
  data: Record<string, any> | null;
};

export type FlowVersionCreate = {
  description?: string | null;
};

export type FlowVersionListResponse = {
  entries: FlowVersionEntry[];
  max_entries: number;
};
