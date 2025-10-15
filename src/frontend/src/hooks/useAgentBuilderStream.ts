import { useState, useCallback, useRef } from "react";

export interface StreamMessage {
  id: string;
  type: "user" | "add_message" | "token" | "end" | "error";
  data: any;
  timestamp: number;
}

export interface StreamState {
  status: "idle" | "connecting" | "streaming" | "complete" | "error";
  messages: StreamMessage[];
  error: string | null;
}

export function useAgentBuilderStream(sessionId?: string) {
  const [state, setState] = useState<StreamState>({
    status: "idle",
    messages: [],
    error: null,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const addMessage = useCallback((type: StreamMessage["type"], data: any) => {
    setState((prev) => {
      // Check if this message ID already exists (Langflow sends updates with same ID)
      const existingIndex = prev.messages.findIndex(
        (msg) => msg.data.id === data.id && data.id
      );

      if (existingIndex !== -1) {
        // Update existing message with new data
        const updatedMessages = [...prev.messages];
        updatedMessages[existingIndex] = {
          ...updatedMessages[existingIndex],
          data,
          timestamp: Date.now(),
        };
        return {
          ...prev,
          messages: updatedMessages,
        };
      }

      // Add new message
      const message: StreamMessage = {
        id: `${Date.now()}-${Math.random()}`,
        type,
        data,
        timestamp: Date.now(),
      };

      return {
        ...prev,
        messages: [...prev.messages, message],
      };
    });
  }, []);

  const startStream = useCallback(
    async (prompt: string) => {
      // Clean up any existing connection
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Add user message
      const userMessage: StreamMessage = {
        id: `${Date.now()}-user`,
        type: "user",
        data: { message: prompt },
        timestamp: Date.now(),
      };

      setState((prev) => ({
        status: "connecting",
        messages: [...prev.messages, userMessage],
        error: null,
      }));

      try {
        // Use agent-builder endpoint which properly proxies to Langflow
        abortControllerRef.current = new AbortController();

        const response = await fetch("/api/v1/genesis-studio/agent-builder/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            prompt,
            session_id: sessionId,
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        setState((prev) => ({ ...prev, status: "streaming" }));

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error("No response body");
        }

        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            setState((prev) => ({ ...prev, status: "complete" }));
            break;
          }

          // Decode the chunk and add to buffer
          buffer += decoder.decode(value, { stream: true });

          // Process complete SSE messages
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || ""; // Keep incomplete message in buffer

          for (const line of lines) {
            if (!line.trim()) continue;

            try {
              // Parse SSE format: "event: type\ndata: {json}"
              const eventMatch = line.match(/event:\s*(\w+)/);
              const dataMatch = line.match(/data:\s*({[\s\S]*})/);

              if (eventMatch && dataMatch) {
                const eventType = eventMatch[1] as StreamMessage["type"];
                const eventData = JSON.parse(dataMatch[1]);

                addMessage(eventType, eventData);

                // If end or error, we're done
                if (eventType === "end") {
                  setState((prev) => ({ ...prev, status: "complete" }));
                } else if (eventType === "error") {
                  setState((prev) => ({
                    ...prev,
                    status: "error",
                    error: eventData.error || "An error occurred",
                  }));
                }
              }
            } catch (e) {
              console.error("Error parsing SSE message:", e, line);
            }
          }
        }
      } catch (error: any) {
        if (error.name === "AbortError") {
          setState((prev) => ({ ...prev, status: "idle" }));
        } else {
          setState((prev) => ({
            ...prev,
            status: "error",
            error: error.message || "Failed to connect to stream",
          }));
        }
      }
    },
    [addMessage, state.messages, sessionId]
  );

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setState((prev) => ({ ...prev, status: "idle" }));
  }, []);

  const reset = useCallback(() => {
    stopStream();
    setState({
      status: "idle",
      messages: [],
      error: null,
    });
  }, [stopStream]);

  return {
    ...state,
    startStream,
    stopStream,
    reset,
    isLoading: state.status === "connecting" || state.status === "streaming",
  };
}
