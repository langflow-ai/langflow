import { useState, useRef, useEffect } from "react";
import { v4 as uuid } from "uuid";
import { getURL } from "@/controllers/API/helpers/constants";
import { Message, FileInputComponent } from "./Playground.types";

export function usePlaygroundChat(publishedFlowData: any) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => uuid());
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [loadingDots, setLoadingDots] = useState(1);
  const [targetTexts, setTargetTexts] = useState<Map<string, string>>(new Map());
  const [displayedTexts, setDisplayedTexts] = useState<Map<string, string>>(new Map());
  
  const targetTextsRef = useRef<Map<string, string>>(new Map());
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    targetTextsRef.current = targetTexts;
  }, [targetTexts]);

  // Loading dots animation for empty streaming messages
  useEffect(() => {
    const hasEmptyStreamingMessage = messages.some(
      (msg) => msg.isStreaming && !msg.text
    );

    if (hasEmptyStreamingMessage) {
      const interval = setInterval(() => {
        setLoadingDots((prev) => (prev % 3) + 1);
      }, 500);

      return () => clearInterval(interval);
    } else {
      setLoadingDots(1);
    }
  }, [messages]);

  // Typewriter effect for streaming text
  useEffect(() => {
    const interval = setInterval(() => {
      setDisplayedTexts((prev) => {
        const next = new Map(prev);
        let hasChanges = false;

        targetTextsRef.current.forEach((target, messageId) => {
          const current = prev.get(messageId) || "";

          if (current.length < target.length) {
            const charsToAdd = Math.min(5, target.length - current.length);
            next.set(messageId, target.substring(0, current.length + charsToAdd));
            hasChanges = true;
          }
        });

        return hasChanges ? next : prev;
      });
    }, 20);

    return () => clearInterval(interval);
  }, []);

  const createFileInputTweaks = (
    fileUrls: Record<string, string>,
    fileInputComponents: FileInputComponent[]
  ) => {
    const tweaks: Record<string, any> = {};

    fileInputComponents.forEach((component) => {
      const fileUrl = fileUrls[component.id];
      if (fileUrl) {
        tweaks[component.id] = {
          input_value: fileUrl,
        };
      }
    });

    return tweaks;
  };

const handleStreamEvent = (eventData: any, localAgentMessageId: string) => {
  const data = eventData?.data;
  if (!data) return;

  if (eventData.event === "add_message") {
    if (data.sender === "User") return;

    if (data.sender === "Machine") {
      const backendId = data.id;
      const text = data.text || "";
      const state = data.properties?.state || "partial";
      const isComplete = state === "complete";

      setTargetTexts((prev) => {
        const next = new Map(prev);
        next.set(backendId, text);
        return next;
      });

      setDisplayedTexts((prev) => {
        if (!prev.has(backendId)) {
          const next = new Map(prev);
          const currentDisplayed = prev.get(localAgentMessageId) || "";
          next.set(backendId, currentDisplayed);
          next.delete(localAgentMessageId);
          return next;
        }
        return prev;
      });

      setMessages((prev) => {
        const existingIndex = prev.findIndex((msg) => msg.id === backendId);

        if (existingIndex !== -1) {
          return prev.map((msg) =>
            msg.id === backendId
              ? {
                  ...msg,
                  text: isComplete ? text : "",
                  isStreaming: !isComplete,
                }
              : msg
          );
        } else {
          const placeholderIndex = prev.findIndex(
            (msg) => msg.id === localAgentMessageId
          );

          if (placeholderIndex !== -1) {
            return prev.map((msg) =>
              msg.id === localAgentMessageId
                ? {
                    ...msg,
                    id: backendId,
                    text: isComplete ? text : "",
                    isStreaming: !isComplete,
                  }
                : msg
            );
          } else {
            return [
              ...prev,
              {
                id: backendId,
                type: "agent" as const,
                text: isComplete ? text : "",
                timestamp: new Date(),
                isStreaming: !isComplete,
              },
            ];
          }
        }
      });

      if (isComplete) {
        setTimeout(() => {
          setTargetTexts((prev) => {
            const next = new Map(prev);
            next.delete(backendId);
            return next;
          });
          setDisplayedTexts((prev) => {
            const next = new Map(prev);
            next.delete(backendId);
            return next;
          });
        }, 2000);
      }
    }
  } else if (eventData.event === "end") {

    try {
      const outputs = data?.result?.outputs;
      if (outputs && outputs.length > 0) {
        const firstOutput = outputs[0];
        const outputResults = firstOutput?.outputs?.[0];
        
        let finalText = "";

        if (outputResults?.results?.text?.data?.text) {
          finalText = outputResults.results.text.data.text;
        }

        else if (outputResults?.results?.text?.text) {
          finalText = outputResults.results.text.text;
        }

        else if (outputResults?.outputs?.text?.message) {
          finalText = outputResults.outputs.text.message;
        }

        else if (outputResults?.messages && outputResults.messages.length > 0) {
          finalText = outputResults.messages[0].message || "";
        }

        if (finalText) {

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === localAgentMessageId
                ? { ...msg, text: finalText, isStreaming: false }
                : msg
            )
          );
          
          // Clear typewriter state
          setTargetTexts(new Map());
          setDisplayedTexts(new Map());
        } else {
          setMessages((prev) =>
            prev.map((msg) => ({ ...msg, isStreaming: false }))
          );
        }
      } else {
        setMessages((prev) =>
          prev.map((msg) => ({ ...msg, isStreaming: false }))
        );
      }
    } catch (error) {
      console.error("[Playground] Error parsing end event:", error);
      setMessages((prev) =>
        prev.map((msg) => ({ ...msg, isStreaming: false }))
      );
    }
  } else if (eventData.event === "error") {
    const errorMsg = data?.error || "Stream error";
    throw new Error(errorMsg);
  }
};

  const sendMessage = async (
    userInputText: string,
    fileUrls: Record<string, string>,
    fileInputComponents: FileInputComponent[]
  ) => {
    if (!userInputText.trim() || isLoading) return;

    const userMessage: Message = {
      id: uuid(),
      type: "user",
      text: userInputText,
      timestamp: new Date(),
    };

    const localAgentMessageId = uuid();
    const agentMessage: Message = {
      id: localAgentMessageId,
      type: "agent",
      text: "",
      timestamp: new Date(),
      isStreaming: true,
    };

    setDisplayedTexts((prev) => {
      const next = new Map(prev);
      next.set(localAgentMessageId, "");
      return next;
    });

    setMessages((prev) => [...prev, userMessage, agentMessage]);
    setIsLoading(true);
    setError(null);
    setStreamingMessageId(localAgentMessageId);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const fileTweaks = createFileInputTweaks(fileUrls, fileInputComponents);

      const requestBody = {
        output_type: "chat",
        input_type: "chat",
        input_value: userInputText,
        session_id: sessionId,
        ...(Object.keys(fileTweaks).length > 0 && { tweaks: fileTweaks }),
      };

      const response = await fetch(
        `${getURL("RUN")}/${publishedFlowData.flow_id}?stream=true`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(requestBody),
          signal: abortController.signal,
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const eventData = JSON.parse(line);
            handleStreamEvent(eventData, localAgentMessageId);
          } catch (e) {
            console.error("[Playground] Error parsing chunk:", e, line);
          }
        }
      }

      if (buffer.trim()) {
        try {
          const eventData = JSON.parse(buffer);
          handleStreamEvent(eventData, localAgentMessageId);
        } catch (e) {
          // Ignore final buffer parsing errors
        }
      }

      setMessages((prev) =>
        prev.map((msg) => ({ ...msg, isStreaming: false }))
      );
    } catch (err: any) {
      console.error("Streaming error:", err);

      if (err.name === "AbortError") {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === localAgentMessageId
              ? { ...msg, text: msg.text + " [stopped]", isStreaming: false }
              : msg
          )
        );
      } else {
        const errorMessage = err.message || "Streaming failed";
        setError(errorMessage);

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === localAgentMessageId
              ? { ...msg, text: `Error: ${errorMessage}`, isStreaming: false }
              : msg
          )
        );
      }
    } finally {
      setIsLoading(false);
      setStreamingMessageId(null);
      abortControllerRef.current = null;
    }
  };

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  return {
    messages,
    isLoading,
    error,
    streamingMessageId,
    loadingDots,
    targetTexts,
    displayedTexts,
    sendMessage,
    stopStreaming,
    setError,
  };
}
