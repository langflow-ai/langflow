import type {
  AgenticFlowUpdateEvent,
  AgenticProgressState,
  AgenticResult,
  AgenticStepType,
  FlowAction,
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
  flowPreview?: {
    flow: Record<string, unknown>;
    name: string;
    nodeCount: number;
    edgeCount: number;
    graph: string;
  };
  flowActions?: FlowAction[];
  pendingFlowProposal?: PendingFlowProposal;
  flowProposalStatus?: FlowProposalStatus;
  writtenFiles?: WrittenFile[];
}

/** A file the agent persisted via write_file or edit_file. */
export interface WrittenFile {
  /** ``"write_file"`` (new/overwrite) or ``"edit_file"`` (in-place substring replace). */
  action: "write_file" | "edit_file";
  /** Path relative to the user's sandbox root. */
  path: string;
  /** File size in bytes after the operation. */
  size: number;
  /** Local timestamp the SSE event was received — for ordering inside the message. */
  receivedAt: number;
  /**
   * Final text content of the file shipped inline with the SSE event so the
   * UI can render it without a second HTTP fetch. Absent for ``edit_file``
   * events (the wrapper doesn't have the post-edit content on hand).
   */
  content?: string;
}

export type FlowProposalStatus = "pending" | "applied" | "dismissed";

export interface PendingFlowProposal {
  flow: Record<string, unknown>;
  name?: string;
  nodeCount: number;
  edgeCount: number;
  /**
   * Events that arrived AFTER the gating set_flow. Per the agent prompt
   * this should never happen, but if it does the tail events are buffered
   * here so they replay in order when the user clicks Continue.
   */
  tailUpdates?: AgenticFlowUpdateEvent[];
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

/** AssistantMessage with Date serialized as ISO string and progress stripped. */
export type SerializedAssistantMessage = Omit<
  AssistantMessage,
  "timestamp" | "progress"
> & {
  timestamp: string;
};

/** A saved session entry stored in localStorage. */
export interface SessionHistoryEntry {
  sessionId: string;
  firstUserMessage: string;
  messageCount: number;
  lastActiveAt: string;
  messages: SerializedAssistantMessage[];
}
