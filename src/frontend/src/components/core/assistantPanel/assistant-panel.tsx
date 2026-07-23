import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { useSidebar } from "@/components/ui/sidebar";
import { useIsFlowReadOnly } from "@/contexts/permissionsContext";
import type { AgenticStepType } from "@/controllers/API/queries/agentic";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import useFlowBuilderWelcomeStore from "@/stores/flowBuilderWelcomeStore";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import type {
  AssistantModel,
  AssistantPanelProps,
} from "./assistant-panel.types";
import { AssistantHeader } from "./components/assistant-header";
import { AssistantInput } from "./components/assistant-input";
import { AssistantMessageItem } from "./components/assistant-message";
import { AssistantNoModelsState } from "./components/assistant-no-models-state";
import { useAssistantChat, useEnabledModels, useSessionHistory } from "./hooks";

// Module-level draft cache — survives panel unmount/remount
let draftMessageCache = "";

const PANEL_SIZE_KEY = "langflow-assistant-panel-size";
const MENTION_PANEL_HEIGHT = "26rem";
const DEFAULT_SIZE = { width: 620, height: 600 };
const MIN_SIZE = { width: 456, height: 400 };
const MAX_SIZE = { width: 900, height: 800 };

function getStoredSize(): { width: number; height: number } {
  try {
    const stored = localStorage.getItem(PANEL_SIZE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed.width && parsed.height) return parsed;
    }
  } catch {
    // ignore
  }
  return DEFAULT_SIZE;
}

interface AssistantInputWithScrollProps {
  onSend: (content: string, model: AssistantModel | null) => void;
  onStop: () => void;
  disabled: boolean;
  isProcessing: boolean;
  currentStep: AgenticStepType | null;
  autoFocus?: boolean;
  draftMessage?: string;
  onDraftChange?: (draft: string) => void;
  isRefiningPlan?: boolean;
}

function AssistantInputWithScroll({
  onSend,
  onStop,
  disabled,
  isProcessing,
  currentStep,
  autoFocus,
  draftMessage,
  onDraftChange,
  isRefiningPlan,
}: AssistantInputWithScrollProps) {
  const { scrollToBottom } = useStickToBottomContext();

  const handleSend = (content: string, model: AssistantModel | null) => {
    scrollToBottom({ animation: "smooth", duration: 300 });
    onSend(content, model);
  };

  return (
    <AssistantInput
      onSend={handleSend}
      onStop={onStop}
      disabled={disabled}
      isProcessing={isProcessing}
      currentStep={currentStep}
      autoFocus={autoFocus}
      draftMessage={draftMessage}
      onDraftChange={onDraftChange}
      isRefiningPlan={isRefiningPlan}
      compact
    />
  );
}

export function AssistantPanel({ isOpen, onClose }: AssistantPanelProps) {
  const { hasEnabledModels } = useEnabledModels();
  const panelRef = useRef<HTMLDivElement>(null);
  const currentFlowId = useFlowStore((state) => state.currentFlow?.id);
  const isReadOnly = useIsFlowReadOnly(currentFlowId);
  // An open sidebar offsets the canvas 280px, so the panel shifts right by
  // half (140px) to stay canvas-centered; collapsed uses plain left-1/2.
  const isSidebarOpen = useSidebar().open;

  useEffect(() => {
    if (isOpen && isReadOnly) onClose();
  }, [isOpen, isReadOnly, onClose]);

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: PointerEvent) => {
      const target = e.target as Node;
      // Don't close if clicking inside the panel
      if (panelRef.current && panelRef.current.contains(target)) return;
      // Don't close if clicking inside a dropdown portal, popover, or dialog
      const el = e.target as HTMLElement;
      if (
        el.closest?.("[role='menu']") ||
        el.closest?.("[data-radix-popper-content-wrapper]")
      )
        return;
      if (
        el.closest?.("[role='dialog']") ||
        el.closest?.("[data-radix-dialog-overlay]")
      )
        return;
      // Don't close if any panel dropdown or dialog is currently open (portals render outside panelRef)
      if (document.querySelector("[data-radix-popper-content-wrapper]")) return;
      if (document.querySelector("[role='dialog']")) return;
      // Don't close if clicking the canvas controls (let the toggle button handle it)
      if (el.closest?.("[data-testid='main_canvas_controls']")) return;
      // Don't close if interacting with a resize handle
      if (el.closest?.("[data-resize-handle]")) return;
      onClose();
    };

    document.addEventListener("pointerdown", handleClickOutside, true);
    return () =>
      document.removeEventListener("pointerdown", handleClickOutside, true);
  }, [isOpen, onClose]);
  const {
    messages,
    sessionId,
    isProcessing,
    currentStep,
    handleSend,
    handleApprove,
    handleUpdateFlowAction,
    handleApplyFlowProposal,
    handleRevertFlowProposal,
    handleDismissFlowProposal,
    handleApprovePlan,
    handleDismissPlan,
    handleResetPlan,
    handleAcknowledgeValidation,
    isRefiningPlan,
    skipAll,
    handleRetry,
    handleMarkReverted,
    handleStopGeneration,
    handleClearHistory,
    loadSession,
  } = useAssistantChat();

  // v1 scope: only the LATEST assistant message with a restore point offers
  // Revert — restoring an older point mid-chain would confuse the timeline.
  const latestRestorePointId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "assistant" && m.restoreVersionId) return m.id;
    }
    return undefined;
  }, [messages]);

  // Sync processing state to store so the canvas can lock during assistant work
  const setAssistantProcessing = useAssistantManagerStore(
    (state) => state.setAssistantProcessing,
  );
  useEffect(() => {
    setAssistantProcessing(isProcessing);
    return () => setAssistantProcessing(false);
  }, [isProcessing, setAssistantProcessing]);

  // Welcome→Assistant hand-off: fire ONE handleSend with the stashed prompt
  // once the panel is open and a model is in localStorage, then clear it.
  const pendingMessage = useFlowBuilderWelcomeStore(
    (state) => state.pendingMessage,
  );
  const clearPendingMessage = useFlowBuilderWelcomeStore(
    (state) => state.clearPendingMessage,
  );
  useEffect(() => {
    if (!isOpen || !pendingMessage || isReadOnly) return;
    let saved: AssistantModel | null = null;
    try {
      const raw = localStorage.getItem("langflow-assistant-selected-model");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.provider && parsed.name) {
          saved = parsed as AssistantModel;
        }
      }
    } catch {
      // localStorage may be unavailable (private browsing); the pending
      // message stays around for a manual retry.
    }
    if (!saved) return;
    void handleSend(pendingMessage, saved);
    clearPendingMessage();
  }, [isOpen, pendingMessage, isReadOnly, handleSend, clearPendingMessage]);

  // Opening with a pendingMessage = welcome submit: lock a min-height so the
  // auto-sent message + reply aren't cramped in the tiny compact panel.
  const [openedWithPending, setOpenedWithPending] = useState(false);
  useEffect(() => {
    if (isOpen && pendingMessage) {
      setOpenedWithPending(true);
    } else if (!isOpen) {
      setOpenedWithPending(false);
    }
  }, [isOpen, pendingMessage]);

  const { sessions, saveCurrentSession, switchSession, deleteSession } =
    useSessionHistory(sessionId, messages, loadSession);

  const handleNewSession = useCallback(() => {
    handleStopGeneration();
    saveCurrentSession();
    draftMessageCache = "";
    handleClearHistory();
  }, [handleStopGeneration, saveCurrentSession, handleClearHistory]);

  const handleApproveAndClose = (messageId: string, componentCode?: string) => {
    if (isReadOnly) return;
    handleApprove(messageId, componentCode);
    onClose();
  };

  const hasMessages = messages.length > 0;
  const [hasExpandedOnce, setHasExpandedOnce] = useState(false);
  const [hasUserResized, setHasUserResized] = useState(false);
  const [isMentionOpen, setIsMentionOpen] = useState(false);

  // Track if panel has ever shown messages (to keep expanded size after new session)
  useEffect(() => {
    if (hasMessages) setHasExpandedOnce(true);
  }, [hasMessages]);

  // Reset when panel is closed
  useEffect(() => {
    if (!isOpen) {
      setHasExpandedOnce(false);
      setHasUserResized(false);
    }
  }, [isOpen]);

  // First handle grab in the empty state flips the panel to expanded, so its
  // dimensions become panelSize-driven instead of auto-fitting the input.
  const useExpandedSize = hasMessages || hasExpandedOnce || hasUserResized;
  const [panelSize, setPanelSize] = useState(getStoredSize);
  const resizeCleanupRef = useRef<(() => void) | null>(null);

  // Clean up resize listeners if the component unmounts mid-drag
  useEffect(() => {
    return () => {
      resizeCleanupRef.current?.();
    };
  }, []);

  const handleEdgeResize = useCallback(
    (e: React.MouseEvent, edges: { x?: "left" | "right"; y?: "top" }) => {
      e.preventDefault();
      e.stopPropagation();
      // Only vertical drags expand the empty panel; horizontal drags widen it.
      // Seed startH from the rendered height or the first pixel snaps 200→600px.
      const startX = e.clientX;
      const startY = e.clientY;
      const startW = panelSize.width;
      let startH = panelSize.height;

      if (edges.y === "top") {
        if (!useExpandedSize && panelRef.current) {
          const measuredH = panelRef.current.getBoundingClientRect().height;
          if (measuredH > 0) {
            startH = measuredH;
            // Push the measured height pre-flip so the first expanded frame
            // renders at the measured height, not the stored default.
            setPanelSize((prev) => ({ ...prev, height: measuredH }));
          }
        }
        setHasUserResized(true);
      }

      // Compact drags start below MIN_SIZE.height; a per-drag floor lets the
      // panel grow smoothly instead of snapping to 400px on first mousemove.
      const effectiveMinH = Math.min(MIN_SIZE.height, startH);

      const handleMouseMove = (ev: MouseEvent) => {
        let newW = startW;
        let newH = startH;

        if (edges.x === "right") {
          newW = startW + (ev.clientX - startX);
        } else if (edges.x === "left") {
          newW = startW - (ev.clientX - startX);
        }

        if (edges.y === "top") {
          newH = startH - (ev.clientY - startY);
        }

        setPanelSize({
          width: Math.min(MAX_SIZE.width, Math.max(MIN_SIZE.width, newW)),
          height: Math.min(MAX_SIZE.height, Math.max(effectiveMinH, newH)),
        });
      };

      const cleanup = () => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
        resizeCleanupRef.current = null;
      };

      const handleMouseUp = () => {
        cleanup();
        setPanelSize((prev) => {
          // Commit at least the floor (state + localStorage) on release:
          // effectiveMinH relaxes it only mid-drag, never for later renders.
          const committed = {
            ...prev,
            height: Math.max(MIN_SIZE.height, prev.height),
          };
          try {
            localStorage.setItem(PANEL_SIZE_KEY, JSON.stringify(committed));
          } catch {
            // localStorage may be unavailable (private browsing)
          }
          return committed;
        });
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      resizeCleanupRef.current = cleanup;
    },
    [panelSize, useExpandedSize],
  );

  if (!isOpen || isReadOnly) return null;

  const containerClasses = cn(
    "flex flex-col transition-[opacity,transform] duration-200 fixed shadow-xl will-change-[opacity,transform]",
    "z-50 bottom-16 -translate-x-1/2 rounded-2xl border border-border",
    isSidebarOpen ? "left-[calc(50%+140px)]" : "left-1/2",
    "opacity-100 translate-y-0 max-w-[calc(100vw-2rem)]",
  );

  // Welcome submits enforce a 300px floor — compact mode would render at the
  // ~200px input height, too short to see the auto-sent message + reply.
  const pendingMinHeight = openedWithPending ? "18.75rem" : undefined;

  const containerStyle = useExpandedSize
    ? {
        width: panelSize.width,
        height: panelSize.height,
        minWidth: "28.5rem",
        minHeight: pendingMinHeight,
        // No inline minHeight: it would clamp BEFORE the resize handler and
        // snap a compact panel; the mousemove clamp enforces the floor.
      }
    : {
        width: panelSize.width,
        minWidth: "28.5rem",
        // Definite height (not just min-height) so the inner ``h-full`` column
        // can bottom-anchor the input, leaving room for the upward popover.
        ...(isMentionOpen
          ? { height: MENTION_PANEL_HEIGHT }
          : { minHeight: pendingMinHeight }),
      };

  return (
    <div
      ref={panelRef}
      data-testid="assistant-panel"
      className={containerClasses}
      style={containerStyle}
    >
      <div className="absolute inset-0 rounded-2xl bg-background" />

      <div className="relative z-10 flex h-full min-h-0 flex-col overflow-hidden">
        <AssistantHeader
          onClose={onClose}
          onNewSession={handleNewSession}
          hasMessages={hasMessages}
          sessions={sessions}
          activeSessionId={sessionId}
          onSelectSession={switchSession}
          onDeleteSession={deleteSession}
          isExpanded={useExpandedSize}
          skipAll={skipAll}
        />
        {!hasEnabledModels && !hasMessages ? (
          <AssistantNoModelsState />
        ) : hasMessages ? (
          <StickToBottom
            className="flex flex-1 flex-col overflow-hidden"
            resize="smooth"
            initial="instant"
          >
            <StickToBottom.Content className="flex min-h-full flex-col justify-end px-4 pt-4 pb-0">
              {messages.map((msg) => (
                <AssistantMessageItem
                  key={msg.id}
                  message={msg}
                  onApprove={handleApproveAndClose}
                  onUpdateFlowAction={handleUpdateFlowAction}
                  onApplyFlowProposal={handleApplyFlowProposal}
                  onRevertFlowProposal={handleRevertFlowProposal}
                  onDismissFlowProposal={handleDismissFlowProposal}
                  onApprovePlan={handleApprovePlan}
                  onDismissPlan={handleDismissPlan}
                  onResetPlan={handleResetPlan}
                  onRetry={hasEnabledModels ? handleRetry : undefined}
                  skipApprovalGate={skipAll}
                  onAcknowledgeValidation={handleAcknowledgeValidation}
                  isLatestRestorePoint={msg.id === latestRestorePointId}
                  onReverted={handleMarkReverted}
                />
              ))}
            </StickToBottom.Content>
            <AssistantInputWithScroll
              onSend={handleSend}
              onStop={handleStopGeneration}
              disabled={!hasEnabledModels || isProcessing}
              isProcessing={isProcessing}
              currentStep={currentStep}
              autoFocus={isOpen && hasEnabledModels}
              draftMessage={draftMessageCache}
              onDraftChange={(draft) => {
                draftMessageCache = draft;
              }}
              isRefiningPlan={isRefiningPlan}
            />
          </StickToBottom>
        ) : (
          <>
            {(useExpandedSize || isMentionOpen) && <div className="flex-1" />}
            <AssistantInput
              onSend={handleSend}
              onStop={handleStopGeneration}
              disabled={false}
              isProcessing={isProcessing}
              currentStep={currentStep}
              compact={hasExpandedOnce}
              autoFocus={isOpen}
              draftMessage={draftMessageCache}
              onDraftChange={(draft) => {
                draftMessageCache = draft;
              }}
              isRefiningPlan={isRefiningPlan}
              onMentionOpenChange={setIsMentionOpen}
            />
          </>
        )}
      </div>

      {/* Edge resize handles — invisible hitboxes with hover highlight.
          Always rendered: the empty state needs them too so the user can
          widen the panel before sending the first message. First drag flips
          hasUserResized → panel transitions from auto-height to
          panelSize-driven dimensions. */}
      <>
        {/* Left edge */}
        <div
          data-resize-handle
          className="absolute top-3 bottom-3 -left-[5px] z-30 w-[10px] cursor-ew-resize rounded-full transition-colors hover:bg-primary/20"
          onMouseDown={(e) => handleEdgeResize(e, { x: "left" })}
        />
        {/* Right edge */}
        <div
          data-resize-handle
          className="absolute top-3 bottom-3 -right-[5px] z-30 w-[10px] cursor-ew-resize rounded-full transition-colors hover:bg-primary/20"
          onMouseDown={(e) => handleEdgeResize(e, { x: "right" })}
        />
        {/* Top edge */}
        <div
          data-resize-handle
          className="absolute -top-[5px] right-3 left-3 z-30 h-[10px] cursor-ns-resize rounded-full transition-colors hover:bg-primary/20"
          onMouseDown={(e) => handleEdgeResize(e, { y: "top" })}
        />
        {/* Top-left corner */}
        <div
          data-resize-handle
          className="absolute -top-[5px] -left-[5px] z-30 h-[14px] w-[14px] cursor-nw-resize rounded-full transition-colors hover:bg-primary/30"
          onMouseDown={(e) => handleEdgeResize(e, { x: "left", y: "top" })}
        />
        {/* Top-right corner */}
        <div
          data-resize-handle
          className="absolute -top-[5px] -right-[5px] z-30 h-[14px] w-[14px] cursor-ne-resize rounded-full transition-colors hover:bg-primary/30"
          onMouseDown={(e) => handleEdgeResize(e, { x: "right", y: "top" })}
        />
      </>
    </div>
  );
}

export default AssistantPanel;
