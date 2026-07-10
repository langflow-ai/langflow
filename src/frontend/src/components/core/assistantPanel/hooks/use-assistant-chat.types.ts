import type { AgenticStepType } from "@/controllers/API/queries/agentic";
import type {
  AssistantMessage,
  AssistantModel,
} from "../assistant-panel.types";

export interface UseAssistantChatReturn {
  messages: AssistantMessage[];
  sessionId: string;
  isProcessing: boolean;
  currentStep: AgenticStepType | null;
  handleSend: (
    content: string,
    model: AssistantModel | null,
    options?: { silent?: boolean },
  ) => Promise<void>;
  handleApprove: (messageId: string, componentCode?: string) => Promise<void>;
  handleUpdateFlowAction: (
    messageId: string,
    actionId: string,
    status: "applied" | "dismissed",
  ) => Promise<void>;
  handleApplyFlowProposal: (
    messageId: string,
    mode?: "replace" | "add",
  ) => void;
  handleRevertFlowProposal: (messageId: string) => void;
  handleDismissFlowProposal: (messageId: string) => void;
  handleApprovePlan: (messageId: string) => Promise<void>;
  handleDismissPlan: (messageId: string) => void;
  handleResetPlan: (messageId: string) => void;
  /**
   * Mark the component validation gate as acknowledged on the message.
   * Persisted across remounts so panel close/reopen doesn't bring the
   * loading card back after the user already pressed Continue.
   */
  handleAcknowledgeValidation: (messageId: string) => void;
  /**
   * True while a previously-proposed plan has been dismissed by the user and
   * is awaiting refinement. The UI uses this to swap the input placeholder
   * and amber the plan card.
   */
  isRefiningPlan: boolean;
  /**
   * Persistent power-user preference: when true, every gate that would
   * otherwise require an explicit Continue click auto-approves. Restored
   * from localStorage on mount.
   */
  skipAll: boolean;
  /** Flip the skipAll preference and persist the change. */
  toggleSkipAll: () => void;
  handleRetry: (messageId: string) => void;
  /** Persist the reverted state on a message after a successful revert. */
  handleMarkReverted: (messageId: string) => void;
  handleStopGeneration: () => void;
  handleClearHistory: () => void;
  loadSession: (id: string, msgs: AssistantMessage[]) => void;
}
