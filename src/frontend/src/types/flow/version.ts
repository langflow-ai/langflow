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
  /** Set by the server (deploys, evaluations, upgrade repairs): the version is never pruned or deleted. */
  retained?: boolean;
  /** Why the version is retained. The list endpoint omits it when null. */
  retained_reason?: string | null;
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
