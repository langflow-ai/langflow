import { useState, useCallback, useRef } from "react";

export interface StreamMessage {
  id: string;
  type: "user" | "thinking" | "agent_found" | "complete" | "error";
  data: any;
  timestamp: number;
}

export interface StreamState {
  status: "idle" | "connecting" | "streaming" | "complete" | "error";
  messages: StreamMessage[];
  error: string | null;
}

export function useAgentBuilderStream() {
  const [state, setState] = useState<StreamState>({
    status: "idle",
    messages: [],
    error: null,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const addMessage = useCallback((type: StreamMessage["type"], data: any) => {
    const message: StreamMessage = {
      id: `${Date.now()}-${Math.random()}`,
      type,
      data,
      timestamp: Date.now(),
    };

    setState((prev) => ({
      ...prev,
      messages: [...prev.messages, message],
    }));
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

      // Add user message first
      const userMessage: StreamMessage = {
        id: `${Date.now()}-user`,
        type: "user",
        data: { message: prompt },
        timestamp: Date.now(),
      };

      setState({
        status: "connecting",
        messages: [userMessage],
        error: null,
      });

      try {
        // Use fetch with ReadableStream instead of EventSource for POST requests
        abortControllerRef.current = new AbortController();

        const response = await fetch("/api/v1/agent-builder/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ prompt }),
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

                // If complete or error, we're done
                if (eventType === "complete") {
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
    [addMessage]
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
