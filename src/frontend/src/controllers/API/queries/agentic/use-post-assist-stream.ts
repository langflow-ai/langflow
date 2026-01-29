import { getURL } from "../../helpers/constants";
import type {
  AgenticAssistRequest,
  AgenticCompleteEvent,
  AgenticErrorEvent,
  AgenticProgressEvent,
  AgenticSSEEvent,
  AgenticTokenEvent,
} from "./types";

interface StreamCallbacks {
  onProgress?: (event: AgenticProgressEvent) => void;
  onToken?: (event: AgenticTokenEvent) => void;
  onComplete?: (event: AgenticCompleteEvent) => void;
  onError?: (event: AgenticErrorEvent) => void;
}

function parseSSEEvent(data: string): AgenticSSEEvent | null {
  try {
    return JSON.parse(data) as AgenticSSEEvent;
  } catch {
    // Malformed JSON from SSE stream - skip this event
    return null;
  }
}

function processSSELine(
  line: string,
  callbacks: StreamCallbacks,
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
    case "progress":
      callbacks.onProgress?.(event);
      break;
    case "token":
      callbacks.onToken?.(event);
      break;
    case "complete":
      callbacks.onComplete?.(event);
      return { done: true };
    case "error":
      callbacks.onError?.(event);
      return { done: true };
  }

  return { done: false };
}

export async function postAssistStream(
  request: AgenticAssistRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const url = getURL("AGENTIC_ASSIST_STREAM");

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
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
      // Error response is plain text, not JSON - use as-is
      errorMessage = errorText || errorMessage;
    }

    callbacks.onError?.({
      event: "error",
      message: errorMessage,
    });
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError?.({
      event: "error",
      message: "No response body",
    });
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");

      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine) {
          const result = processSSELine(trimmedLine, callbacks);
          if (result.done) {
            return;
          }
        }
      }
    }

    // Process any remaining data in the buffer
    if (buffer.trim()) {
      processSSELine(buffer.trim(), callbacks);
    }
  } finally {
    reader.releaseLock();
  }
}
