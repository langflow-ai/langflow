import { useCallback, useRef, useState } from "react";
import ShortUniqueId from "short-unique-id";
import { postAgentChatStream } from "@/controllers/API/queries/agents";
import type { AgentMessage, AgentModel } from "../types";

const uid = new ShortUniqueId();

interface UseAgentChatReturn {
  messages: AgentMessage[];
  isProcessing: boolean;
  handleSend: (content: string, model: AgentModel | null) => Promise<void>;
  handleStopGeneration: () => void;
  handleClearHistory: () => void;
}

export function useAgentChat(agentId: string | null): UseAgentChatReturn {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string>(uid.randomUUID(16));

  const handleSend = useCallback(
    async (content: string, model: AgentModel | null) => {
      if (isProcessing || !agentId || !model?.provider || !model?.name) return;

      const userMessage: AgentMessage = {
        id: uid.randomUUID(10),
        role: "user",
        content,
        timestamp: new Date(),
        status: "complete",
      };

      const agentMessageId = uid.randomUUID(10);
      const agentMessage: AgentMessage = {
        id: agentMessageId,
        role: "agent",
        content: "",
        timestamp: new Date(),
        status: "streaming",
      };

      setMessages((prev) => [...prev, userMessage, agentMessage]);
      setIsProcessing(true);

      abortControllerRef.current = new AbortController();

      try {
        await postAgentChatStream(
          agentId,
          {
            input_value: content,
            provider: model.provider,
            model_name: model.name,
            session_id: sessionIdRef.current,
          },
          {
            onToken: (event) => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === agentMessageId
                    ? { ...msg, content: msg.content + event.chunk }
                    : msg,
                ),
              );
            },
            onComplete: () => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === agentMessageId
                    ? { ...msg, status: "complete" }
                    : msg,
                ),
              );
              setIsProcessing(false);
            },
            onError: (event) => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === agentMessageId
                    ? { ...msg, status: "error", error: event.message }
                    : msg,
                ),
              );
              setIsProcessing(false);
            },
            onCancelled: () => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === agentMessageId
                    ? { ...msg, status: "cancelled" }
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
              msg.id === agentMessageId
                ? { ...msg, status: "error", error: "Failed to connect" }
                : msg,
            ),
          );
        }
        setIsProcessing(false);
      }
    },
    [isProcessing, agentId],
  );

  const handleStopGeneration = useCallback(() => {
    abortControllerRef.current?.abort();
    setMessages((prev) =>
      prev.map((msg) =>
        msg.status === "streaming" ? { ...msg, status: "cancelled" } : msg,
      ),
    );
    setIsProcessing(false);
  }, []);

  const handleClearHistory = useCallback(() => {
    abortControllerRef.current?.abort();
    setMessages([]);
    setIsProcessing(false);
    sessionIdRef.current = uid.randomUUID(16);
  }, []);

  return {
    messages,
    isProcessing,
    handleSend,
    handleStopGeneration,
    handleClearHistory,
  };
}
