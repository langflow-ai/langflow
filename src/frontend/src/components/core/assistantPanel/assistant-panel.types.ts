import type {
  AgenticProgressState,
  AgenticResult,
  AgenticStepType,
} from "@/controllers/API/queries/agentic";

export type AssistantMessageStatus =
  | "pending"
  | "streaming"
  | "complete"
  | "error"
  | "cancelled";

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  status?: AssistantMessageStatus;
  progress?: AgenticProgressState;
  completedSteps?: AgenticStepType[];
  result?: AgenticResult;
  error?: string;
}

export interface AssistantModel {
  id: string;
  name: string;
  provider: string;
  displayName: string;
}

export interface AssistantSuggestion {
  id: string;
  icon: string;
  text: string;
}

export interface AssistantPanelProps {
  isOpen: boolean;
  onClose: () => void;
}
