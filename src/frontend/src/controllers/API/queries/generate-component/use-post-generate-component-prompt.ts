import { useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { GenerateComponentPromptResponse, ProgressState } from "@/components/core/generateComponent/types";

const SSE_DATA_PREFIX = "data: ";
const SSE_EVENT_SEPARATOR = "\n\n";

type GenerateComponentPromptRequest = {
  flowId: string;
  inputValue: string;
  componentId?: string;
  fieldName?: string;
  maxRetries?: number;
  provider?: string;
  modelName?: string;
};

type StreamingRequest = GenerateComponentPromptRequest & {
  onProgress?: (progress: ProgressState) => void;
};

type SSEEvent = {
  event: "progress" | "complete" | "error";
  step?: "generating" | "validating";
  attempt?: number;
  max_attempts?: number;
  data?: GenerateComponentPromptResponse;
  message?: string;
};

async function postGenerateComponentPrompt({
  flowId,
  inputValue,
  componentId,
  fieldName,
  maxRetries,
  provider,
  modelName,
}: GenerateComponentPromptRequest): Promise<GenerateComponentPromptResponse> {
  const response = await api.post<GenerateComponentPromptResponse>(
    getURL("GENERATE_COMPONENT_PROMPT"),
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

export async function postGenerateComponentPromptStream({
  flowId,
  inputValue,
  componentId,
  fieldName,
  maxRetries,
  provider,
  modelName,
  onProgress,
}: StreamingRequest): Promise<GenerateComponentPromptResponse> {
  const response = await fetchStreamingResponse({
    flowId,
    inputValue,
    componentId,
    fieldName,
    maxRetries,
    provider,
    modelName,
  });

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  return processSSEStream(reader, onProgress);
}

async function fetchStreamingResponse(
  request: GenerateComponentPromptRequest,
): Promise<Response> {
  const baseUrl = api.defaults.baseURL || "";
  const url = `${baseUrl}${getURL("GENERATE_COMPONENT_PROMPT_STREAM")}`;

  const axiosHeaders = api.defaults.headers.common as Record<string, string>;
  const authHeader = axiosHeaders?.Authorization
    ? { Authorization: axiosHeaders.Authorization }
    : {};

  const response = await fetch(url, {
    method: "POST",
    headers: {
      ...authHeader,
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify({
      flow_id: request.flowId,
      input_value: request.inputValue,
      component_id: request.componentId,
      field_name: request.fieldName,
      max_retries: request.maxRetries,
      provider: request.provider,
      model_name: request.modelName,
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
): Promise<GenerateComponentPromptResponse> {
  const decoder = new TextDecoder();
  let result: GenerateComponentPromptResponse | null = null;
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
): GenerateComponentPromptResponse | null {
  for (const line of eventBlock.split("\n")) {
    if (!line.startsWith(SSE_DATA_PREFIX)) continue;

    const jsonStr = line.slice(SSE_DATA_PREFIX.length);
    const event = parseSSEEvent(jsonStr);
    if (!event) continue;

    if (event.event === "error") {
      throw new Error(event.message || "Unknown error");
    }

    if (event.event === "progress" && onProgress && event.step && event.attempt && event.max_attempts) {
      onProgress({
        step: event.step,
        attempt: event.attempt,
        maxAttempts: event.max_attempts,
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

export function usePostGenerateComponentPrompt() {
  return useMutation({
    mutationFn: postGenerateComponentPrompt,
    mutationKey: ["usePostGenerateComponentPrompt"],
  });
}
