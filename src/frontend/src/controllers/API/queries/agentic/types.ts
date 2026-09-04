export type AgenticStepType =
  | "generating"
  | "generating_component"
  | "generating_plan"
  | "generating_flow"
  | "orchestrating"
  | "generation_complete"
  | "extracting_code"
  | "validating"
  | "validated"
  | "validation_failed"
  | "retrying"
  | "searching_components"
  | "building_flow"
  | "flow_built"
  | "flow_build_failed"
  | "flow_proposal_ready"
  | "generating_document"
  | "document_ready";

export interface AgenticProgressEvent {
  event: "progress";
  step: AgenticStepType;
  attempt: number;
  max_attempts: number;
  message?: string;
  error?: string;
  class_name?: string;
  component_code?: string;
}

export interface AgenticTokenEvent {
  event: "token";
  chunk: string;
}

export interface AgenticCompleteData {
  result: string;
  validated: boolean;
  class_name?: string;
  component_code?: string;
  validation_attempts?: number;
  validation_error?: string;
  has_flow?: boolean;
  /** Backend-computed: a deferred step (e.g. run) was requested with an
   * edit, so approving a man-in-the-loop edit should fire the continuation
   * turn. Absent/false for a pure edit. */
  continuation_expected?: boolean;
  /** Accumulated LLM token usage for the whole turn — TranslationFlow
   * classification + every agent attempt. Same shape as the playground's
   * message metadata (``properties.usage``) so the ``MessageMetadata`` badge
   * is reused unchanged. Absent only if no LLM call ran on this turn. */
  usage?: {
    input_tokens?: number | null;
    output_tokens?: number | null;
    total_tokens?: number | null;
  };
  /** Wall-clock duration of the turn, measured server-side around the whole
   * pipeline. Rendered as the duration half of the cost badge. */
  duration_seconds?: number;
  /** Flow version snapshotted BEFORE a canvas-mutating turn — a rollback
   * point restorable via the flow versions API/UI. Absent for question
   * turns, empty canvases, or when snapshotting failed. */
  restore_version_id?: string;
  /** Non-fatal model errors this turn recovered from (the chosen model failed
   * silently in the background and the assistant fell back / retried). Rendered
   * as an (i) next to the message so the swap is not hidden. Absent when the
   * chosen model worked. */
  notices?: AssistantModelNotice[];
}

export interface AgenticFlowPreviewEvent {
  event: "flow_preview";
  flow: Record<string, unknown>;
  name: string;
  node_count: number;
  edge_count: number;
  graph: string;
}

export interface AgenticFlowUpdateEvent {
  event: "flow_update";
  action:
    | "add_component"
    | "remove_component"
    | "connect"
    | "configure"
    | "set_flow"
    | "edit_field"
    | "select_output"
    | "set_connection_mode"
    | "enable_tool_mode"
    | "propose_plan";
  /** Backend sets this on a compound-pipeline set_flow so the canvas is
   * replaced directly (the user already asked to clear+replace it) —
   * no Continue/Dismiss proposal card. */
  auto_apply?: boolean;
  [key: string]: unknown;
}

/**
 * Emitted the moment a canvas-mutating agent tool STARTS executing, so the
 * UI can show a live "currently doing X" row. Additive — the matching
 * flow_update (or the run ending) retires it.
 */
export interface AgenticToolStartEvent {
  event: "tool_start";
  /** Backend tool name, e.g. "add_component", "build_flow". */
  tool: string;
  /** English fallback label; the UI prefers its own i18n by tool name. */
  label?: string;
  component_type?: string;
  component_id?: string;
  source_id?: string;
  target_id?: string;
  field?: string;
}

/** Emitted by the agent's sandboxed write_file / edit_file tools. */
export interface AgenticFileWrittenEvent {
  event: "file_written";
  action: "write_file" | "edit_file";
  /** Path relative to the user's sandbox root — never absolute. */
  path: string;
  /** File size in bytes after the operation. */
  size: number;
  /**
   * Final text content of the file (when the wrapper had it on hand —
   * always for write_file, currently absent for edit_file). Lets the
   * frontend render the body inline without a second HTTP fetch.
   */
  content?: string;
}

export interface FlowAction {
  id: string;
  type: "edit_field";
  description: string;
  component_id: string;
  component_type: string;
  field: string;
  old_value: unknown;
  new_value: unknown;
  patch: { op: string; path: string; value: unknown }[];
  status: "pending" | "applied" | "dismissed";
}

/** A silent, recovered model failure surfaced to the user. */
export interface AssistantModelNotice {
  /** ``model_fallback`` (swapped to another model) or ``model_remediation``
   * (retried the same model with adjusted params). */
  type: "model_fallback" | "model_remediation" | string;
  /** User-facing friendly reason (e.g. "requires a subscription"). */
  reason: string;
  /** The model the user selected that failed. */
  failed_model?: string;
  /** The model that actually produced the answer (fallback only). */
  used_model?: string;
}

export interface AgenticCompleteEvent {
  event: "complete";
  data: AgenticCompleteData;
}

/** Additive structured-failure context on the SSE error event. All fields
 * optional — older backends simply omit ``detail`` and only ``message`` renders. */
export interface AgenticErrorDetail {
  /** Last progress step the backend emitted before failing. */
  step?: string;
  /** Component the backend was building/running when it failed. */
  component_id?: string;
  /** Tool involved in the failure, when extractable. */
  tool?: string;
  /** Pre-truncation error string (capped server-side at 2000 chars). */
  raw_cause?: string;
  /** Recommended next step mapped from the known error categories. */
  recommendation?: string;
}

export interface AgenticErrorEvent {
  event: "error";
  message: string;
  detail?: AgenticErrorDetail;
}

export interface AgenticCancelledEvent {
  event: "cancelled";
  message: string;
}

export type AgenticSSEEvent =
  | AgenticProgressEvent
  | AgenticTokenEvent
  | AgenticCompleteEvent
  | AgenticFlowPreviewEvent
  | AgenticFlowUpdateEvent
  | AgenticToolStartEvent
  | AgenticFileWrittenEvent
  | AgenticErrorEvent
  | AgenticCancelledEvent;

export interface AgenticAssistRequest {
  flow_id: string;
  input_value: string;
  model_name?: string;
  provider?: string;
  max_retries?: number;
  session_id?: string;
  history_limit?: number;
  /** Agent step budget for this turn (`/iterations N`); the backend clamps to
   * 1–200 and falls back to the flow default when absent. */
  iterations_limit?: number;
}

export interface AgenticProgressState {
  step: AgenticStepType;
  attempt: number;
  maxAttempts: number;
  message?: string;
  error?: string;
  className?: string;
  componentCode?: string;
}

export interface AgenticResult {
  content: string;
  validated: boolean;
  className?: string;
  componentCode?: string;
  validationError?: string;
  validationAttempts?: number;
  hasFlow?: boolean;
  flowData?: Record<string, unknown>;
  flowName?: string;
}
