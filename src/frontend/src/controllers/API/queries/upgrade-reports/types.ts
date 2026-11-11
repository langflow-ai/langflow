export type JobUsage = {
  runs: number | null;
  errors: number | null;
  last_run_at: string | null;
  history: "retained_records" | "no_retained_records" | "unavailable";
  coverage: {
    oldest_retained_at: string | null;
    newest_retained_at: string | null;
    observed_at: string;
    complete: false;
    retention_days: number | null;
  };
  limitations: string[];
};

export type ReportFlow = {
  id: string;
  kind: "flow" | "component" | "flow_version";
  name: string | null;
  owner: { id: string | null; username: string | null } | null;
  project: { id: string; name: string | null } | null;
  last_edited_at: string | null;
  status: "ok" | "warn" | "fail";
  nodes: {
    id: string;
    group_path: string[];
    type: string;
    display_name: string;
    status: string;
    reasons: { code: string; message: string | null }[];
    dry_run: { result: string } | null;
  }[];
  flow_id: string | null;
  version_number: number | null;
  used_by: Record<string, string[]> | null;
  labels?: string[] | null;
  usage?: { editor: JobUsage; serving: JobUsage };
  error: string | null;
};

export type ReportDocument = {
  format_version: 1;
  generated_at: string;
  source: {
    dialect: string;
    identity?: {
      kind: string;
      locator: Record<string, string | number | null>;
      sha256: string;
    };
    alembic_revision: string | null;
  };
  target: {
    langflow: string;
    lfx: string;
    component_index_sha256: string;
    bundles: string[];
  };
  summary: {
    flows: { ok: number; warn: number; fail: number };
    nodes: Record<string, number>;
  };
  flows: ReportFlow[];
  errors: { kind: string; status: string; message: string }[];
};

export type ReportEntry = {
  id: string;
  created_at: string;
  generated_at: string;
  target_version: string;
  source_identity: string | null;
  flow_count: number;
  warning_count: number;
  failing_count: number;
};
export type ReportHistory = {
  items: ReportEntry[];
  total: number;
  offset: number;
  limit: number;
};
export type ReportDetail = ReportEntry & { document: ReportDocument };
export type RepairStatus =
  | "ready"
  | "updated"
  | "unchanged"
  | "manual"
  | "conflict"
  | "forbidden"
  | "not_found"
  | "failed";
export type RepairResult = {
  flow_id: string;
  status: RepairStatus;
  version_token: string | null;
  data_sha256: string | null;
  updated_nodes: number;
  recovery_version_id: string | null;
  reason_codes: string[];
};
export type RepairPreview = {
  target_sha256: string;
  target_version?: string;
  results: RepairResult[];
};
export type RepairOutcome = {
  id: string;
  created_at: string;
  created_by: string | null;
  target_sha256: string;
  result: RepairResult;
};
