import { getURL } from "../../helpers/constants";
import type {
  AgentCancelledEvent,
  AgentChatStreamRequest,
  AgentCompleteEvent,
  AgentErrorEvent,
  AgentSSEEvent,
  AgentTokenEvent,
} from "./types";

interface AgentStreamCallbacks {
  onToken?: (event: AgentTokenEvent) => void;
  onComplete?: (event: AgentCompleteEvent) => void;
  onError?: (event: AgentErrorEvent) => void;
  onCancelled?: (event: AgentCancelledEvent) => void;
}

function parseSSEEvent(data: string): AgentSSEEvent | null {
  try {
    return JSON.parse(data) as AgentSSEEvent;
  } catch {
    return null;
  }
}

function processSSELine(
  line: string,
  callbacks: AgentStreamCallbacks,
): { done: boolean } {
  if (!line.startsWith("data: ")) {
    return { done: false };
  }

  const data = line.slice(6);
  const event = parseSSEEvent(data);

  if (!event) {
    return { done: false };
  }

  switch (event.event) {
    case "token":
      callbacks.onToken?.(event);
      break;
    case "complete":
      callbacks.onComplete?.(event);
      return { done: true };
    case "error":
      callbacks.onError?.(event);
      return { done: true };
    case "cancelled":
      callbacks.onCancelled?.(event);
      return { done: true };
  }

  return { done: false };
}

export async function postAgentChatStream(
  agentId: string,
  request: AgentChatStreamRequest,
  callbacks: AgentStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const params = new URLSearchParams();
  params.set("input_value", request.input_value);
  if (request.provider) params.set("provider", request.provider);
  if (request.model_name) params.set("model_name", request.model_name);
  if (request.session_id) params.set("session_id", request.session_id);

  const url = `${getURL("AGENTS")}/${agentId}/chat/stream?${params.toString()}`;

  const response = await fetch(url, {
    method: "POST",
    headers: { Accept: "text/event-stream" },
    credentials: "include",
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    let errorMessage = "Request failed";

    try {
      const errorJson = JSON.parse(errorText);
      errorMessage = errorJson.detail || errorJson.message || errorMessage;
    } catch {
      errorMessage = errorText || errorMessage;
    }

    callbacks.onError?.({ event: "error", message: errorMessage });
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError?.({ event: "error", message: "No response body" });
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine) {
          const result = processSSELine(trimmedLine, callbacks);
          if (result.done) return;
        }
      }
    }

    if (buffer.trim()) {
      processSSELine(buffer.trim(), callbacks);
    }
  } finally {
    reader.releaseLock();
  }
}
