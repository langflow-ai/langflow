export type AgenticStepType =
  | "generating"
  | "generating_component"
  | "generation_complete"
  | "extracting_code"
  | "validating"
  | "validated"
  | "validation_failed"
  | "retrying";

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
}

export interface AgenticResult {
  content: string;
  validated: boolean;
  className?: string;
  componentCode?: string;
  validationError?: string;
  validationAttempts?: number;
}
