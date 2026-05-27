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
  /** A deferred follow-up (e.g. run) was requested alongside an edit, so
   * approving a man-in-the-loop edit on this message resumes via the
   * continuation turn. False for a pure edit (no redundant 2nd message). */
  continuationExpected?: boolean;
  pendingFlowProposal?: PendingFlowProposal;
  flowProposalStatus?: FlowProposalStatus;
  pendingPlanProposal?: PendingPlanProposal;
  planProposalStatus?: PlanProposalStatus;
  writtenFiles?: WrittenFile[];
  /**
   * Live checklist of incremental canvas mutations the agent performed
   * (add/remove/connect/configure). Populated as the SSE stream lands;
   * the UI renders this as a checkboxed task list above the markdown.
   * Excludes the destructive ``set_flow`` proposal path — that goes
   * through the dedicated Continue/Dismiss card.
   */
  buildTasks?: BuildTask[];
  /**
   * Skip rendering this message entirely. Used by skip-all to suppress
   * the propose_plan turn's preamble — the user never sees the "I am
   * proposing a plan and waiting" content that the LLM streams before
   * the tool call.
   */
  hidden?: boolean;
  /**
   * True once the user has acknowledged the "Component ready" / validation
   * gate — either by clicking Continue or by the 30s auto-dismiss timer
   * firing. Persisted on the message so panel close/reopen (which
   * remounts the item) doesn't bring the gate back. Without this, local
   * state would reset and the user would see the loading card again on
   * every reopen.
   */
  validationAcknowledged?: boolean;
  /** Per-turn LLM cost reported by the backend on the ``complete`` SSE event.
   * Used by ``MessageMetadata`` (the playground's renderer, reused here) to
   * display the token-count + duration badge with the breakdown tooltip. */
  usage?: {
    input_tokens?: number | null;
    output_tokens?: number | null;
    total_tokens?: number | null;
  };
  /** Wall-clock duration of the turn in milliseconds (already converted from
   * the backend's ``duration_seconds``). Same units that ``MessageMetadata``
   * expects in the playground. */
  duration?: number;
}

/** A single incremental canvas operation surfaced to the user as a task. */
export type BuildTaskAction =
  | "add_component"
  | "remove_component"
  | "connect"
  | "configure";

export interface BuildTask {
  /** Canvas action that produced this entry. */
  action: BuildTaskAction;
  /** Subject component id for add/remove/configure. */
  componentId?: string;
  /** Friendly type label for add (e.g. "ChatInput"). */
  componentType?: string;
  /** Source endpoint for connect. */
  sourceId?: string;
  /** Target endpoint for connect. */
  targetId?: string;
  /** Local timestamp the SSE event was received — for ordering. */
  receivedAt: number;
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

/**
 * Status of the BUILD-mode planning gate that runs BEFORE the agent calls
 * search/describe/build_flow.
 *
 * - "pending"    — card shows Continue/Dismiss; agent is waiting.
 * - "refining"   — user clicked Dismiss; card stays visible with Continue +
 *                  Reset, and the next user message carries the prior plan
 *                  markdown as context so the agent (which has no server-side
 *                  conversation history) can replan with full awareness.
 * - "approved"   — user clicked Continue; agent resumed and is building.
 * - "dismissed"  — user clicked Reset on a refining card; planning gate is
 *                  closed, stash cleared, no prior plan re-injected.
 */
export type PlanProposalStatus =
  | "pending"
  | "refining"
  | "approved"
  | "dismissed";

export interface PendingPlanProposal {
  /** Raw markdown emitted by the agent's propose_plan tool. */
  markdown: string;
}

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
