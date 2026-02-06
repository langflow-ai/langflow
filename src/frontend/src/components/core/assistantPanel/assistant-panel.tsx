import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import type { AgenticStepType } from "@/controllers/API/queries/agentic";
import { cn } from "@/utils/utils";
import type {
  AssistantModel,
  AssistantPanelProps,
} from "./assistant-panel.types";
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
    />
  );
}

export function AssistantPanel({ isOpen, onClose }: AssistantPanelProps) {
  const { viewMode, setViewMode } = useAssistantViewMode();
  const { hasEnabledModels } = useEnabledModels();
  const {
    messages,
    isProcessing,
    currentStep,
    handleSend,
    handleApprove,
    handleStopGeneration,
    handleClearHistory,
  } = useAssistantChat();

  const handleSuggestionClick = (suggestion: string) => {
    handleSend(suggestion, null);
  };

  const hasMessages = messages.length > 0;

  // Fixed positioning for both modes - always rendered, position changes based on viewMode
  const containerClasses = cn(
    "flex flex-col transition-all duration-300 fixed shadow-xl",
    viewMode === "sidebar"
      ? cn(
          "left-0 top-[49px] z-[60] h-[calc(100%-49px)] w-[500px]",
          isOpen ? "translate-x-0" : "-translate-x-full",
        )
      : cn(
          "z-50 bottom-20 left-[calc(50%+140px)] -translate-x-1/2 w-[520px] rounded-2xl border border-border",
          hasMessages ? "h-[500px]" : "h-auto",
          isOpen
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-4 pointer-events-none",
        ),
  );

  return (
    <div className={containerClasses}>
      <div
        className={cn(
          "absolute inset-0 bg-background",
          viewMode === "floating" && "rounded-2xl",
        )}
      />

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
              currentStep={currentStep}
            />
          </StickToBottom>
        ) : viewMode === "floating" ? (
          <AssistantInput
            onSend={handleSend}
            onStop={handleStopGeneration}
            disabled={false}
            isProcessing={isProcessing}
            currentStep={currentStep}
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
              currentStep={currentStep}
            />
          </>
        )}
      </div>
    </div>
  );
}

export default AssistantPanel;
