export type AgenticStepType =
  | "generating"
  | "generating_component"
  | "generating_flow"
  | "generation_complete"
  | "extracting_code"
  | "extracting_flow"
  | "validating"
  | "validating_flow"
  | "validated"
  | "validated_flow"
  | "validation_failed"
  | "retrying";

export interface CompactFlowNode {
  id: string;
  type: string;
  values?: Record<string, unknown>;
}

export interface CompactFlowEdge {
  source: string;
  source_output: string;
  target: string;
  target_input: string;
}

export interface CompactFlowData {
  nodes: CompactFlowNode[];
  edges: CompactFlowEdge[];
}

export interface ExpandedFlowData {
  nodes: unknown[];
  edges: unknown[];
}

export interface AgenticProgressEvent {
  event: "progress";
  step: AgenticStepType;
  attempt: number;
  max_attempts: number;
  message?: string;
  error?: string;
  class_name?: string;
  component_code?: string;
  flow_data?: CompactFlowData;
  expanded_flow?: ExpandedFlowData;
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
  flow_validated?: boolean;
  flow_data?: CompactFlowData;
  expanded_flow?: ExpandedFlowData;
  node_count?: number;
  edge_count?: number;
  warnings?: string[] | null;
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
  flowData?: CompactFlowData;
  expandedFlow?: ExpandedFlowData;
}

export interface AgenticResult {
  content: string;
  validated: boolean;
  className?: string;
  componentCode?: string;
  validationError?: string;
  validationAttempts?: number;
  flowValidated?: boolean;
  flowData?: CompactFlowData;
  expandedFlow?: ExpandedFlowData;
  nodeCount?: number;
  edgeCount?: number;
}
