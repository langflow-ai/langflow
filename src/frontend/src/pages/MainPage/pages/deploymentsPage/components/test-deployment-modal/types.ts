export interface ToolTrace {
  toolName: string;
  input: unknown;
  output: unknown;
  agentName?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolTraces?: ToolTrace[];
  isLoading?: boolean;
  error?: string;
}
