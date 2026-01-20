import { useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { AssistantPromptResponse, ProgressState, ProgressStep } from "@/components/core/assistant/assistant.types";

const SSE_DATA_PREFIX = "data: ";
const SSE_EVENT_SEPARATOR = "\n\n";

type AssistantPromptRequest = {
  flowId: string;
  inputValue: string;
  componentId?: string;
  fieldName?: string;
  maxRetries?: number;
  provider?: string;
  modelName?: string;
  sessionId?: string;
};

type StreamingRequest = AssistantPromptRequest & {
  onProgress?: (progress: ProgressState) => void;
  abortSignal?: AbortSignal;
};

type SSEEvent = {
  event: "progress" | "complete" | "error";
  step?: ProgressStep;
  attempt?: number;
  max_attempts?: number;
  message?: string;        // Human-readable status message
  error?: string;          // Error message (for validation_failed/retrying)
  class_name?: string;     // Class name (for validation_failed)
  component_code?: string; // Component code (for validation_failed)
  data?: AssistantPromptResponse;
};

async function postAssistantPrompt({
  flowId,
  inputValue,
  componentId,
  fieldName,
  maxRetries,
  provider,
  modelName,
}: AssistantPromptRequest): Promise<AssistantPromptResponse> {
  const response = await api.post<AssistantPromptResponse>(
    getURL("ASSISTANT_PROMPT"),
    {
      flow_id: flowId,
      input_value: inputValue,
      component_id: componentId,
      field_name: fieldName,
      max_retries: maxRetries,
      provider,
      model_name: modelName,
    },
  );
  return response.data;
}

export async function postAssistantPromptStream({
  flowId,
  inputValue,
  componentId,
  fieldName,
  maxRetries,
  provider,
  modelName,
  sessionId,
  onProgress,
  abortSignal,
}: StreamingRequest): Promise<AssistantPromptResponse> {
  const response = await fetchStreamingResponse(
    {
      flowId,
      inputValue,
      componentId,
      fieldName,
      maxRetries,
      provider,
      modelName,
      sessionId,
    },
    abortSignal,
  );

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  return processSSEStream(reader, onProgress);
}

async function fetchStreamingResponse(
  request: AssistantPromptRequest,
  abortSignal?: AbortSignal,
): Promise<Response> {
  const baseUrl = api.defaults.baseURL || "";
  const url = `${baseUrl}${getURL("ASSISTANT_PROMPT_STREAM")}`;

  const axiosHeaders = api.defaults.headers.common as Record<string, string>;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (axiosHeaders?.Authorization) {
    headers.Authorization = axiosHeaders.Authorization;
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
    signal: abortSignal,
    body: JSON.stringify({
      flow_id: request.flowId,
      input_value: request.inputValue,
      component_id: request.componentId,
      field_name: request.fieldName,
      max_retries: request.maxRetries,
      provider: request.provider,
      model_name: request.modelName,
      session_id: request.sessionId,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error ${response.status}`);
  }

  return response;
}

async function processSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onProgress?: (progress: ProgressState) => void,
): Promise<AssistantPromptResponse> {
  const decoder = new TextDecoder();
  let result: AssistantPromptResponse | null = null;
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const { events, remaining } = splitSSEEvents(buffer);
    buffer = remaining;

    for (const eventBlock of events) {
      result = processSSEEvent(eventBlock, onProgress) ?? result;
    }
  }

  if (buffer.trim()) {
    result = processSSEEvent(buffer, onProgress) ?? result;
  }

  if (!result) {
    throw new Error("No response received");
  }

  return result;
}

function splitSSEEvents(buffer: string): { events: string[]; remaining: string } {
  const parts = buffer.split(SSE_EVENT_SEPARATOR);
  const remaining = parts.pop() || "";
  return { events: parts, remaining };
}

function processSSEEvent(
  eventBlock: string,
  onProgress?: (progress: ProgressState) => void,
): AssistantPromptResponse | null {
  for (const line of eventBlock.split("\n")) {
    if (!line.startsWith(SSE_DATA_PREFIX)) continue;

    const jsonStr = line.slice(SSE_DATA_PREFIX.length);
    const event = parseSSEEvent(jsonStr);
    if (!event) continue;

    if (event.event === "error") {
      throw new Error(event.message || "Unknown error");
    }

    if (event.event === "progress" && onProgress && event.step) {
      onProgress({
        step: event.step,
        attempt: event.attempt ?? 1,
        maxAttempts: event.max_attempts ?? 1,
        message: event.message,
        error: event.error,
        componentName: event.class_name,
        componentCode: event.component_code,
      });
    }

    if (event.event === "complete" && event.data) {
      return event.data;
    }
  }

  return null;
}

function parseSSEEvent(jsonStr: string): SSEEvent | null {
  try {
    return JSON.parse(jsonStr) as SSEEvent;
  } catch {
    return null;
  }
}

export function usePostAssistantPrompt() {
  return useMutation({
    mutationFn: postAssistantPrompt,
    mutationKey: ["usePostAssistantPrompt"],
  });
}
