export type AgenticStepType =
  | "generating"
  | "generating_component"
  | "generating_flow"
  | "generation_complete"
  | "extracting_code"
  | "validating"
  | "validated"
  | "validation_failed"
  | "retrying"
  | "searching_components"
  | "building_flow"
  | "flow_built"
  | "flow_build_failed";

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
    | "edit_field";
  [key: string]: unknown;
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
