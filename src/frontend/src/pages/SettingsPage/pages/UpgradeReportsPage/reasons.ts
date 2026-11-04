const categories: Record<string, string> = {
  malformed_graph: "invalid",
  malformed_node: "invalid",
  malformed_group: "invalid",
  malformed_edge: "invalid",
  malformed_flow: "invalid",
  duplicate_node_id: "invalid",
  blocked: "policy",
  owner_policy_denied: "policy",
  authorization_denied: "policy",
  retired: "retired",
  outdated_breaking: "preservation",
  preservation_failed: "preservation",
  customized_nodes_skipped: "customized",
  owner_unavailable: "owner",
  flow_locked: "managed",
  file_backed_flow: "managed",
  repair_prerequisite_unavailable: "unavailable",
  repair_unavailable: "unavailable",
  database_unavailable: "unavailable",
  database_busy: "changed",
  source_changed: "changed",
  outcome_record_unavailable: "outcome",
};
export const repairReasonKey = (code: string): string =>
  `settings.upgrade.reason.${categories[code] ?? "failed"}`;

const usageCategories: Record<string, string> = {
  retention_policy_unknown: "retentionUnknown",
  executions_without_job_records_untracked: "untrackedUsage",
  run_time_is_job_created_at: "jobTime",
  job_timestamps_invalid: "invalidJobTime",
  preserved_editor_flow_id_not_observed: "unmatchedServing",
  cancelled_start_unknown: "unclassifiedJobs",
  unknown_job_status_excluded: "unclassifiedJobs",
  unclassified_job_type_excluded: "unclassifiedJobs",
  job_flow_id_invalid: "unclassifiedJobs",
};
export const usageReasonKey = (code: string): string | null =>
  code === "retained_jobs_only"
    ? null
    : `settings.upgrade.${usageCategories[code] ?? "historyUnavailable"}`;
