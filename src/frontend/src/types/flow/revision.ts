/** A flow's operation history, as served by `/api/v1/flows/{id}/revisions`. */

export type RevisionActor = {
  id: string;
  /** Null when the user has since been deleted. */
  username: string | null;
};

export type RecordedOperation = {
  revision: number;
  actor: RevisionActor;
  request_id: string;
  /**
   * Why the change happened, when an action caused it: `upgrade_component`,
   * `edit_code`, `file_sync`, `restore`, `assistant` or `repair`. A display
   * hint only.
   */
  cause?: string;
  /** The operation as recorded, with literal secret values removed. */
  operation: Record<string, unknown> & { type: string };
  /** Display names of the nodes it touched, as they were when it was recorded. */
  labels: {
    nodes?: Record<string, string>;
    edges?: Record<string, { source: string; target: string }>;
  };
};

export type RevisionVersion = {
  id: string;
  version_number: number;
  version_tag: string;
  description: string | null;
  created_at: string;
  operation_revision: number;
  saved_by: RevisionActor | null;
};

export type RevisionEntry = {
  id: string;
  start_revision: number;
  /** The revision this entry can be previewed at or restored to. */
  end_revision: number;
  created_at: string | null;
  actors: RevisionActor[];
  request_ids: string[];
  versions: RevisionVersion[];
  operations: RecordedOperation[] | null;
};

export type RevisionPage = {
  flow_id: string;
  latest_revision: number;
  current_revision: number;
  /** The first revision still retained; null before the flow has history. */
  earliest_revision: number | null;
  entries: RevisionEntry[];
  next_before: number | null;
};

export type RevisionGraph = {
  flow_id: string;
  revision: number;
  latest_revision: number;
  data: Record<string, unknown>;
};
