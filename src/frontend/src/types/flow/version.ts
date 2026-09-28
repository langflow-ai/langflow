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
  // biome-ignore lint/suspicious/noExplicitAny: serialized flow data, shape varies by component
  data: Record<string, any> | null;
};

export type FlowVersionCreate = {
  description?: string | null;
};

export type FlowVersionListResponse = {
  entries: FlowVersionEntry[];
  max_entries: number;
};

export type FlowVersionDiffSideKind = "version" | "draft";

export type FlowVersionDiffSideRef = {
  kind: FlowVersionDiffSideKind;
  version_id?: string | null;
  version_number?: number | null;
  version_tag?: string | null;
  description?: string | null;
  created_at?: string | null;
};

export type FlowVersionDiffSummary = {
  nodes_added: number;
  nodes_removed: number;
  nodes_modified: number;
  nodes_unchanged: number;
  edges_added: number;
  edges_removed: number;
  edges_unchanged: number;
  fields_changed: number;
  code_fields_changed: number;
  secrets_changed: number;
};

export type FlowVersionDiffNodeRef = {
  id: string;
  display_name?: string | null;
  component_type?: string | null;
  node_type?: string | null;
};

export type FlowVersionDiffValueChange = {
  before?: string | null;
  after?: string | null;
};

/**
 * `before` and `after` are absent when `redacted` is true — the scrubber touched
 * the value, so the change is reported without disclosing it. Read `redacted`
 * before reading either side.
 */
export type FlowVersionDiffFieldChange = {
  name: string;
  display_name?: string | null;
  status: "added" | "removed" | "modified";
  redacted: boolean;
  before?: unknown;
  after?: unknown;
  before_truncated: boolean;
  after_truncated: boolean;
};

export type FlowVersionDiffCodeChange = {
  field_name: string;
  display_name?: string | null;
  added_lines: number;
  removed_lines: number;
  unified_diff?: string | null;
  truncated: boolean;
  redacted: boolean;
};

export type FlowVersionDiffNodeChange = FlowVersionDiffNodeRef & {
  display_name_change?: FlowVersionDiffValueChange | null;
  field_changes: FlowVersionDiffFieldChange[];
  code_changes: FlowVersionDiffCodeChange[];
  other_changed_keys: string[];
};

export type FlowVersionDiffEdgeRef = {
  id: string;
  source?: string | null;
  target?: string | null;
  source_handle_name?: string | null;
  target_handle_name?: string | null;
};

export type FlowVersionDiff = {
  base: FlowVersionDiffSideRef;
  target: FlowVersionDiffSideRef;
  summary: FlowVersionDiffSummary;
  nodes: {
    added: FlowVersionDiffNodeRef[];
    removed: FlowVersionDiffNodeRef[];
    modified: FlowVersionDiffNodeChange[];
  };
  edges: {
    added: FlowVersionDiffEdgeRef[];
    removed: FlowVersionDiffEdgeRef[];
  };
  identical: boolean;
  truncated: boolean;
};
