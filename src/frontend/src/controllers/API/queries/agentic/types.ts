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

export interface AgenticCompleteEvent {
  event: "complete";
  data: AgenticCompleteData;
}

export interface AgenticErrorEvent {
  event: "error";
  message: string;
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
