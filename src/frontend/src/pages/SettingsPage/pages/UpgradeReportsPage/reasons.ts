import { isAxiosError } from "axios";

const requestErrors: Record<string, { status: number; key: string }> = {
  "Wait for running jobs to finish before applying repairs": {
    status: 409,
    key: "settings.upgrade.runningJobsRefusal",
  },
  "Enable database maintenance before applying repairs": {
    status: 409,
    key: "settings.upgrade.freezeRequired",
  },
  "The instance migration pause does not permit repairs": {
    status: 503,
    key: "settings.upgrade.freezeRequired",
  },
  "The target registry changed. Preview the selected flows again": {
    status: 409,
    key: "settings.upgrade.targetChanged",
  },
  "The flow changed during repair": {
    status: 409,
    key: "settings.upgrade.flowChanged",
  },
};

export function repairRequestErrorKey(error: unknown): string {
  if (isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data?.detail;
    const known =
      typeof detail === "string" ? requestErrors[detail] : undefined;
    if (known && known.status === error.response?.status) return known.key;
  }
  return "settings.upgrade.repairError";
}

const categories: Record<string, string> = {
  malformed_graph: "invalid",
  malformed_node: "invalid",
  malformed_group: "invalid",
  malformed_edge: "invalid",
  malformed_flow: "invalid",
  duplicate_node_id: "invalid",
  blocked: "policy",
  owner_policy_denied: "policy",
  provider_selection_unverifiable: "providerSelection",
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
