export type AgentMessageStatus =
  | "pending"
  | "streaming"
  | "complete"
  | "error"
  | "cancelled";

export interface AgentMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: Date;
  status: AgentMessageStatus;
  error?: string;
}

export interface AgentModel {
  id: string;
  name: string;
  provider: string;
  displayName: string;
}
