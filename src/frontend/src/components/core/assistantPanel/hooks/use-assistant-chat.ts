import { useCallback, useRef, useState } from "react";
import ShortUniqueId from "short-unique-id";
import {
  type AgenticStepType,
  postAssistStream,
} from "@/controllers/API/queries/agentic";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { useAddComponent } from "@/hooks/use-add-component";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { APIClassType } from "@/types/api";
import type {
  AssistantMessage,
  AssistantModel,
} from "../assistant-panel.types";
import { useAssistantSessionId } from "./use-assistant-session-id";

const uid = new ShortUniqueId();

interface UseAssistantChatReturn {
  messages: AssistantMessage[];
  isProcessing: boolean;
  currentStep: AgenticStepType | null;
  handleSend: (content: string, model: AssistantModel | null) => Promise<void>;
  handleApprove: (messageId: string) => Promise<void>;
  handleStopGeneration: () => void;
  handleClearHistory: () => void;
}

export function useAssistantChat(): UseAssistantChatReturn {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState<AgenticStepType | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const { sessionId, resetSessionId } = useAssistantSessionId(
    currentFlowId || "",
  );
  const addComponent = useAddComponent();
  const { mutateAsync: validateComponent } = usePostValidateComponentCode();

  const handleSend = useCallback(
    async (content: string, model: AssistantModel | null) => {
      if (isProcessing) return;

      // Validate model has required fields to prevent backend from using wrong provider
      if (!model?.provider || !model?.name) {
        console.warn(
          "AssistantChat: No model selected, request may use default provider",
        );
      }

      const userMessage: AssistantMessage = {
        id: uid.randomUUID(10),
        role: "user",
        content,
        timestamp: new Date(),
        status: "complete",
      };

      const assistantMessageId = uid.randomUUID(10);
      const assistantMessage: AssistantMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        status: "streaming",
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsProcessing(true);

      abortControllerRef.current = new AbortController();

      const completedSteps: AgenticStepType[] = [];

      try {
        await postAssistStream(
          {
            flow_id: currentFlowId || "",
            input_value: content,
            provider: model?.provider,
            model_name: model?.name,
            session_id: sessionId,
          },
          {
            onProgress: (event) => {
              if (event.step !== completedSteps[completedSteps.length - 1]) {
                if (completedSteps.length > 0) {
                  completedSteps.push(
                    completedSteps[completedSteps.length - 1],
                  );
                }
              }

              setCurrentStep(event.step);
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
              setCurrentStep(null);
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
              setCurrentStep(null);
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
              setCurrentStep(null);
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
        setCurrentStep(null);
        setIsProcessing(false);
      }
    },
    [isProcessing, currentFlowId, sessionId],
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
    abortControllerRef.current?.abort();

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
    setCurrentStep(null);
    setIsProcessing(false);
  }, []);

  const handleClearHistory = useCallback(() => {
    abortControllerRef.current?.abort();
    setMessages([]);
    setCurrentStep(null);
    setIsProcessing(false);
    resetSessionId();
  }, [resetSessionId]);

  return {
    messages,
    isProcessing,
    currentStep,
    handleSend,
    handleApprove,
    handleStopGeneration,
    handleClearHistory,
  };
}
