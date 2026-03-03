export interface AgentRead {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  tool_components: string[];
  icon: string | null;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface AgentCreate {
  name: string;
  description?: string | null;
  system_prompt?: string;
  tool_components?: string[];
  icon?: string | null;
}

export interface AgentUpdate {
  name?: string;
  description?: string | null;
  system_prompt?: string;
  tool_components?: string[];
  icon?: string | null;
}

export interface AgentToolInfo {
  class_name: string;
  display_name: string;
  description: string;
  icon: string;
  category: string;
  is_suggested: boolean;
}

export interface AgentChatStreamRequest {
  input_value: string;
  provider?: string;
  model_name?: string;
  session_id?: string;
}

export interface AgentTokenEvent {
  event: "token";
  chunk: string;
}

export interface AgentCompleteEvent {
  event: "complete";
  data: Record<string, unknown>;
}

export interface AgentErrorEvent {
  event: "error";
  message: string;
}

export interface AgentCancelledEvent {
  event: "cancelled";
  message: string;
}

export type AgentSSEEvent =
  | AgentTokenEvent
  | AgentCompleteEvent
  | AgentErrorEvent
  | AgentCancelledEvent;
