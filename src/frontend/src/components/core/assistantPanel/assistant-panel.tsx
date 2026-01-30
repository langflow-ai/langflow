import { useCallback, useMemo, useRef, useState } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import {
  postAssistStream,
  type AgenticStepType,
} from "@/controllers/API/queries/agentic";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { useAddComponent } from "@/hooks/use-add-component";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { APIClassType } from "@/types/api";
import { cn } from "@/utils/utils";
import type {
  AssistantMessage,
  AssistantModel,
  AssistantPanelProps,
} from "./assistant-panel.types";
import { AssistantEmptyState } from "./components/assistant-empty-state";
import { AssistantHeader } from "./components/assistant-header";
import { AssistantInput } from "./components/assistant-input";
import { AssistantMessageItem } from "./components/assistant-message";
import { AssistantNoModelsState } from "./components/assistant-no-models-state";

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
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { data: providersData = [] } = useGetModelProviders({});
  const { data: enabledModelsData } = useGetEnabledModels();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const addComponent = useAddComponent();
  const { mutateAsync: validateComponent } = usePostValidateComponentCode();

  // Check if there are any enabled models available
  const hasEnabledModels = useMemo(() => {
    const enabledModels = enabledModelsData?.enabled_models || {};

    return providersData.some((provider) => {
      if (!provider.is_enabled) return false;
      const providerEnabledModels = enabledModels[provider.provider] || {};
      return provider.models.some(
        (model) =>
          providerEnabledModels[model.model_name] === true &&
          !model.model_name.includes("embedding"),
      );
    });
  }, [providersData, enabledModelsData]);

  const handleSend = useCallback(
    async (content: string, model: AssistantModel | null) => {
      if (isProcessing) return;

      // Add user message
      const userMessage: AssistantMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content,
        timestamp: new Date(),
        status: "complete",
      };

      // Add assistant message placeholder
      const assistantMessageId = crypto.randomUUID();
      const assistantMessage: AssistantMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        status: "streaming",
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsProcessing(true);

      // Create abort controller for cancellation
      abortControllerRef.current = new AbortController();

      const completedSteps: AgenticStepType[] = [];

      try {
        await postAssistStream(
          {
            flow_id: currentFlowId || "",
            input_value: content,
            provider: model?.provider,
            model_name: model?.name,
          },
          {
            onProgress: (event) => {
              // Track completed steps
              if (event.step !== completedSteps[completedSteps.length - 1]) {
                if (completedSteps.length > 0) {
                  completedSteps.push(completedSteps[completedSteps.length - 1]);
                }
              }

              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        progress: {
                          step: event.step,
                          attempt: event.attempt,
                          maxAttempts: event.max_attempts,
                        },
                        completedSteps: [...completedSteps],
                      }
                    : msg,
                ),
              );
            },
            onToken: (event) => {
              // Append token chunk to message content for real-time streaming
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        content: msg.content + event.chunk,
                      }
                    : msg,
                ),
              );
            },
            onComplete: (event) => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        status: "complete",
                        content: event.data.result || "",
                        result: {
                          content: event.data.result || "",
                          validated: event.data.validated,
                          className: event.data.class_name,
                          componentCode: event.data.component_code,
                          validationAttempts: event.data.validation_attempts,
                          validationError: event.data.validation_error,
                        },
                      }
                    : msg,
                ),
              );
              setIsProcessing(false);
            },
            onError: (event) => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        status: "error",
                        error: event.message,
                      }
                    : msg,
                ),
              );
              setIsProcessing(false);
            },
            onCancelled: () => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        status: "cancelled",
                        progress: undefined,
                      }
                    : msg,
                ),
              );
              setIsProcessing(false);
            },
          },
          abortControllerRef.current.signal,
        );
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    status: "error",
                    error: "Failed to connect to assistant",
                  }
                : msg,
            ),
          );
        }
        setIsProcessing(false);
      }
    },
    [isProcessing, currentFlowId],
  );

  const handleApprove = useCallback(
    async (messageId: string) => {
      const message = messages.find((m) => m.id === messageId);
      if (!message?.result?.componentCode) return;

      try {
        const response = await validateComponent({
          code: message.result.componentCode,
          frontend_node: {} as APIClassType,
        });

        if (response.data) {
          addComponent(response.data, response.type || "CustomComponent");
        }
      } catch {
        // Error is already visible to user via component validation UI
      }
    },
    [messages, validateComponent, addComponent],
  );

  const handleStopGeneration = useCallback(() => {
    // Abort the request
    abortControllerRef.current?.abort();

    // Find the streaming message and mark it as cancelled
    setMessages((prev) =>
      prev.map((msg) =>
        msg.status === "streaming"
          ? {
              ...msg,
              status: "cancelled",
              progress: undefined,
            }
          : msg,
      ),
    );
    setIsProcessing(false);
  }, []);

  const handleSuggestionClick = (suggestion: string) => {
    handleSend(suggestion, null);
  };

  const handleClearHistory = () => {
    // Cancel any ongoing request
    abortControllerRef.current?.abort();
    setMessages([]);
    setIsProcessing(false);
  };

  const hasMessages = messages.length > 0;

  return (
    <div
      className={cn(
        "fixed left-0 top-12 z-50 flex h-[calc(100%-48px)] w-[500px] flex-col shadow-xl transition-transform duration-300",
        isOpen ? "translate-x-0" : "-translate-x-full",
      )}
    >
      {/* Background */}
      <div className="absolute inset-0 overflow-hidden bg-background">
        {/* Gradient glow at bottom */}
        <div
          className="absolute -left-6 bottom-0 h-[505px] w-[936px] blur-[48px]"
          style={{
            background: "linear-gradient(89deg, #19F0A5 0%, #BA75FF 50%, #0FE3FF 100%)",
            opacity: 0.18,
            transform: "rotate(89.1deg)",
          }}
        />
        {/* Noise overlay - very subtle */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          }}
        />
      </div>
      {/* Content */}
      <div className="relative z-10 flex h-full flex-col">
        <AssistantHeader onClose={onClose} onClearHistory={handleClearHistory} disabled={isProcessing} />
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
