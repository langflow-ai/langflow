import { useEffect, useRef, useState } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import type { AgenticStepType } from "@/controllers/API/queries/agentic";
import { cn } from "@/utils/utils";
import type {
  AssistantModel,
  AssistantPanelProps,
} from "./assistant-panel.types";
import { AssistantHeader } from "./components/assistant-header";
import { AssistantInput } from "./components/assistant-input";
import { AssistantMessageItem } from "./components/assistant-message";
import { AssistantNoModelsState } from "./components/assistant-no-models-state";
import {
  useAssistantChat,
  useEnabledModels,
} from "./hooks";

interface AssistantInputWithScrollProps {
  onSend: (content: string, model: AssistantModel | null) => void;
  onStop: () => void;
  disabled: boolean;
  isProcessing: boolean;
  currentStep: AgenticStepType | null;
}

function AssistantInputWithScroll({
  onSend,
  onStop,
  disabled,
  isProcessing,
  currentStep,
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
      compact
    />
  );
}

export function AssistantPanel({ isOpen, onClose }: AssistantPanelProps) {
  const { hasEnabledModels } = useEnabledModels();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: PointerEvent) => {
      const target = e.target as Node;
      // Don't close if clicking inside the panel
      if (panelRef.current && panelRef.current.contains(target)) return;
      // Don't close if clicking inside a dropdown portal or popover
      const el = e.target as HTMLElement;
      if (el.closest?.("[role='menu']") || el.closest?.("[data-radix-popper-content-wrapper]")) return;
      // Don't close if any panel dropdown is currently open (portals render outside panelRef)
      if (document.querySelector("[data-radix-popper-content-wrapper]")) return;
      // Don't close if clicking the canvas controls (let the toggle button handle it)
      if (el.closest?.("[data-testid='main_canvas_controls']")) return;
      onClose();
    };

    document.addEventListener("pointerdown", handleClickOutside, true);
    return () => document.removeEventListener("pointerdown", handleClickOutside, true);
  }, [isOpen, onClose]);
  const {
    messages,
    isProcessing,
    currentStep,
    handleSend,
    handleApprove,
    handleStopGeneration,
    handleClearHistory,
  } = useAssistantChat();

  const handleApproveAndClose = (messageId: string) => {
    handleApprove(messageId);
    onClose();
  };

  const hasMessages = messages.length > 0;
  const [hasExpandedOnce, setHasExpandedOnce] = useState(false);

  // Track if panel has ever shown messages (to keep expanded size after new session)
  useEffect(() => {
    if (hasMessages) setHasExpandedOnce(true);
  }, [hasMessages]);

  // Reset when panel is closed
  useEffect(() => {
    if (!isOpen) setHasExpandedOnce(false);
  }, [isOpen]);

  const useExpandedSize = hasMessages || hasExpandedOnce;

  const containerClasses = cn(
    "flex flex-col transition-all duration-300 fixed shadow-xl",
    "z-50 bottom-16 left-[calc(50%+140px)] -translate-x-1/2 rounded-2xl border border-border",
    useExpandedSize ? "h-[600px] w-[620px]" : "h-auto w-[520px]",
    isOpen
      ? "opacity-100 translate-y-0"
      : "opacity-0 translate-y-4 pointer-events-none",
  );

  return (
    <div ref={panelRef} className={containerClasses}>
      <div className="absolute inset-0 rounded-2xl bg-background" />

      <div className="relative z-10 flex h-full min-h-0 flex-col overflow-hidden">
        <AssistantHeader
          onClose={onClose}
          onNewSession={handleClearHistory}
          hasMessages={hasMessages}
        />
        {!hasEnabledModels ? (
          <>
            <div className="flex flex-1 flex-col overflow-hidden">
              <AssistantNoModelsState />
            </div>
            <AssistantInput
              onSend={handleSend}
              disabled={true}
              placeholder="Configure Model Providers..."
            />
          </>
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
                />
              ))}
            </StickToBottom.Content>
            <AssistantInputWithScroll
              onSend={handleSend}
              onStop={handleStopGeneration}
              disabled={isProcessing}
              isProcessing={isProcessing}
              currentStep={currentStep}
            />
          </StickToBottom>
        ) : (
          <AssistantInput
            onSend={handleSend}
            onStop={handleStopGeneration}
            disabled={false}
            isProcessing={isProcessing}
            currentStep={currentStep}
            compact={hasExpandedOnce}
          />
        )}
      </div>
    </div>
  );
}

export default AssistantPanel;
