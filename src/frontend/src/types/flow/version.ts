export type FlowVersionEntry = {
  id: string;
  flow_id: string;
  user_id: string;
  version_number: number;
  version_tag: string;
  description: string | null;
  created_at: string;
  /** Resolved server-side; absent for versions whose author was deleted. */
  username?: string | null;
  /** The history revision this version's graph belongs to; null if saved before the flow had history. */
  operation_revision?: number | null;
  /** The kept original of a repaired flow: viewable and exportable, not restorable. */
  view_only?: boolean;
};

export type FlowVersionEntryWithData = FlowVersionEntry & {
  data: Record<string, unknown> | null;
};

export type FlowVersionCreate = {
  description?: string | null;
  /** The graph to archive. Omitted, the server snapshots what it already has. */
  data?: Record<string, unknown> | null;
};

export type FlowVersionListResponse = {
  entries: FlowVersionEntry[];
  max_entries: number;
};
