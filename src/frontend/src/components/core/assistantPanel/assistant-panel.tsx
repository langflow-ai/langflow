import { useCallback, useEffect, useRef, useState } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { useSidebar } from "@/components/ui/sidebar";
import type { AgenticStepType } from "@/controllers/API/queries/agentic";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import useFlowBuilderWelcomeStore from "@/stores/flowBuilderWelcomeStore";
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
  // Mirror the FlowPage sidebar's open state. When the sidebar is expanded
  // the canvas is offset 280px from the viewport's left edge, so the panel
  // shifts right by half that (140px) to align with the canvas center. When
  // collapsed (offcanvas slid off), the canvas takes the full viewport and
  // the panel sits at plain ``left-1/2``.
  const isSidebarOpen = useSidebar().open;

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
    handleDismissFlowProposal,
    handleApprovePlan,
    handleDismissPlan,
    handleResetPlan,
    handleAcknowledgeValidation,
    isRefiningPlan,
    skipAll,
    handleRetry,
    handleStopGeneration,
    handleClearHistory,
    loadSession,
  } = useAssistantChat();

  // Sync processing state to store so the canvas can lock during assistant work
  const setAssistantProcessing = useAssistantManagerStore(
    (state) => state.setAssistantProcessing,
  );
  useEffect(() => {
    setAssistantProcessing(isProcessing);
    return () => setAssistantProcessing(false);
  }, [isProcessing, setAssistantProcessing]);

  // Welcome → Assistant hand-off: when the user submits text from the
  // FlowBuilderWelcome overlay, the typed prompt is stashed as
  // ``pendingMessage`` and the panel is told to open. Once the panel is
  // visible AND a model is available (read from localStorage so we don't
  // race the ModelSelector's auto-select effect), fire a single
  // ``handleSend`` with the pending text, then clear so a remount or
  // re-open doesn't replay it.
  const pendingMessage = useFlowBuilderWelcomeStore(
    (state) => state.pendingMessage,
  );
  const clearPendingMessage = useFlowBuilderWelcomeStore(
    (state) => state.clearPendingMessage,
  );
  useEffect(() => {
    if (!isOpen || !pendingMessage) return;
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
      // localStorage may be unavailable (private browsing) — fall through;
      // handleSend will early-return on null model and the welcome's pending
      // message stays around for a manual retry.
    }
    if (!saved) return;
    void handleSend(pendingMessage, saved);
    clearPendingMessage();
  }, [isOpen, pendingMessage, handleSend, clearPendingMessage]);

  // When the panel opens with a pendingMessage in the store, the user just
  // submitted from the welcome overlay. Capture that and lock a min-height
  // so the panel doesn't open in its tiny compact form — the user has just
  // committed an intent and needs vertical room for their auto-sent message
  // + the assistant's reply to render without feeling cramped.
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

  // Once the user grabs a handle in the empty state, treat the panel as
  // expanded so its dimensions become driven by panelSize (instead of
  // auto-fitting to the input height).
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
      // Only vertical drags transition the empty panel into expanded mode
      // (height becomes panelSize-driven, input is pushed to the bottom).
      // Horizontal-only drags should just widen the auto-height panel.
      //
      // Seed startH from the actual rendered height (not panelSize.height)
      // when promoting from compact mode. The compact panel is auto-sized to
      // the input (~200px) while panelSize.height carries the *expanded*
      // default/stored value (~600px). Without this seed, the first pixel of
      // drag flips useExpandedSize and snaps the panel from ~200px to 600px
      // in one frame — visible as a "glitch" jump on first resize after open.
      const startX = e.clientX;
      const startY = e.clientY;
      const startW = panelSize.width;
      let startH = panelSize.height;

      if (edges.y === "top") {
        if (!useExpandedSize && panelRef.current) {
          const measuredH = panelRef.current.getBoundingClientRect().height;
          if (measuredH > 0) {
            startH = measuredH;
            // Push the measured height into state before the flip so the
            // very first frame after useExpandedSize becomes true renders at
            // the measured height instead of the stored expanded default.
            setPanelSize((prev) => ({ ...prev, height: measuredH }));
          }
        }
        setHasUserResized(true);
      }

      // When the user starts dragging the compact panel taller, the measured
      // start height is below ``MIN_SIZE.height``. Clamping to MIN_SIZE.height
      // on the very first mousemove would snap the panel from ~200px to 400px
      // in one frame. The per-drag effective floor lets the panel grow
      // smoothly from its current size while still preventing the user from
      // shrinking BELOW where they started.
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
          // Clamp to the absolute floor in BOTH in-memory state and the
          // persisted localStorage value. The per-drag ``effectiveMinH``
          // intentionally lets a compact-promoted drag stay below
          // ``MIN_SIZE.height`` while the mouse is held; once the user
          // releases, the panel commits to at least the floor so a later
          // transition (e.g. loaded session messages flipping
          // ``useExpandedSize`` to true) doesn't render the panel
          // uncomfortably small.
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

  if (!isOpen) return null;

  const containerClasses = cn(
    "flex flex-col transition-[opacity,transform] duration-200 fixed shadow-xl will-change-[opacity,transform]",
    "z-50 bottom-16 -translate-x-1/2 rounded-2xl border border-border",
    isSidebarOpen ? "left-[calc(50%+140px)]" : "left-1/2",
    "opacity-100 translate-y-0 max-w-[calc(100vw-2rem)]",
  );

  // When the panel was opened from a welcome submit, enforce a 18.75rem
  // (300px) floor so the auto-sent message + assistant reply have room to
  // breathe. Compact-mode (no messages yet) would otherwise render at the
  // input height (~200px) — too short for the user to see what's happening.
  const pendingMinHeight = openedWithPending ? "18.75rem" : undefined;

  const containerStyle = useExpandedSize
    ? {
        width: panelSize.width,
        height: panelSize.height,
        minWidth: "28.5rem",
        minHeight: pendingMinHeight,
        // No inline ``minHeight`` here — that would clamp the rendered height
        // BEFORE the resize handler runs, snapping a freshly-promoted compact
        // panel from its measured ~200px straight to MIN_SIZE.height in one
        // frame. The mousemove clamp (``effectiveMinH``) enforces the floor
        // for actual user drags instead. (Exception: the welcome-submit
        // override above intentionally clamps.)
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
                  onDismissFlowProposal={handleDismissFlowProposal}
                  onApprovePlan={handleApprovePlan}
                  onDismissPlan={handleDismissPlan}
                  onResetPlan={handleResetPlan}
                  onRetry={hasEnabledModels ? handleRetry : undefined}
                  skipApprovalGate={skipAll}
                  onAcknowledgeValidation={handleAcknowledgeValidation}
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
