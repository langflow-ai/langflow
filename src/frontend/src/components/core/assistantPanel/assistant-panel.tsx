import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { cn } from "@/utils/utils";
import type { AssistantModel, AssistantPanelProps } from "./assistant-panel.types";
import { AssistantEmptyState } from "./components/assistant-empty-state";
import { AssistantHeader } from "./components/assistant-header";
import { AssistantInput } from "./components/assistant-input";
import { AssistantMessageItem } from "./components/assistant-message";
import { AssistantNoModelsState } from "./components/assistant-no-models-state";
import {
  useAssistantChat,
  useAssistantViewMode,
  useEnabledModels,
} from "./hooks";

interface AssistantInputWithScrollProps {
  onSend: (content: string, model: AssistantModel | null) => void;
  onStop: () => void;
  disabled: boolean;
  isProcessing: boolean;
}

function AssistantInputWithScroll({
  onSend,
  onStop,
  disabled,
  isProcessing,
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
    />
  );
}

export function AssistantPanel({ isOpen, onClose }: AssistantPanelProps) {
  const { viewMode, setViewMode } = useAssistantViewMode();
  const { hasEnabledModels } = useEnabledModels();
  const {
    messages,
    isProcessing,
    handleSend,
    handleApprove,
    handleStopGeneration,
    handleClearHistory,
  } = useAssistantChat();

  const handleSuggestionClick = (suggestion: string) => {
    handleSend(suggestion, null);
  };

  const hasMessages = messages.length > 0;

  const containerClasses = cn(
    "fixed z-50 flex flex-col shadow-xl transition-all duration-300",
    viewMode === "sidebar"
      ? cn(
          "left-0 top-12 h-[calc(100%-48px)] w-[500px]",
          isOpen ? "translate-x-0" : "-translate-x-full",
        )
      : cn(
          "bottom-4 left-1/2 -translate-x-1/2 w-[650px] rounded-2xl border border-border",
          hasMessages ? "h-[500px]" : "h-auto",
          isOpen ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none",
        ),
  );

  return (
    <div className={containerClasses}>
      <div
        className={cn(
          "absolute inset-0 overflow-hidden bg-background",
          viewMode === "floating" && "rounded-2xl",
        )}
      >
        <div
          className="absolute -left-6 bottom-0 h-[505px] w-[936px] blur-[48px]"
          style={{
            background: "linear-gradient(89deg, #19F0A5 0%, #BA75FF 50%, #0FE3FF 100%)",
            opacity: 0.18,
            transform: "rotate(89.1deg)",
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          }}
        />
      </div>

      <div className="relative z-10 flex h-full min-h-0 flex-col overflow-hidden">
        <AssistantHeader
          onClose={onClose}
          onClearHistory={handleClearHistory}
          disabled={isProcessing}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
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
            <StickToBottom.Content className="flex-1 px-4 py-6">
              {messages.map((msg) => (
                <AssistantMessageItem
                  key={msg.id}
                  message={msg}
                  onApprove={handleApprove}
                />
              ))}
            </StickToBottom.Content>
            <AssistantInputWithScroll
              onSend={handleSend}
              onStop={handleStopGeneration}
              disabled={isProcessing}
              isProcessing={isProcessing}
            />
          </StickToBottom>
        ) : viewMode === "floating" ? (
          <AssistantInput
            onSend={handleSend}
            onStop={handleStopGeneration}
            disabled={false}
            isProcessing={isProcessing}
          />
        ) : (
          <>
            <div className="flex flex-1 flex-col overflow-hidden">
              <AssistantEmptyState onSuggestionClick={handleSuggestionClick} />
            </div>
            <AssistantInput
              onSend={handleSend}
              onStop={handleStopGeneration}
              disabled={false}
              isProcessing={isProcessing}
            />
          </>
        )}
      </div>
    </div>
  );
}

export default AssistantPanel;
