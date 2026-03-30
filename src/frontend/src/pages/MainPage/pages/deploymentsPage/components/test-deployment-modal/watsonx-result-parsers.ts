import type { ToolTrace } from "./types";

export type WatsonxContentItem = {
  type?: string;
  response_type?: string;
  text?: string;
};

export type WatsonxMessage = {
  content?: WatsonxContentItem[];
  context?: { wxo_thread_id?: string };
  thread_id?: string;
  step_history?: Array<{
    step_details?: Array<{
      tool_use?: { name: string; input: unknown };
      tool_result?: { output: unknown };
    }>;
  }>;
};

export type WatsonxData = {
  message?: WatsonxMessage;
  thread_id?: string;
};

export type WatsonxResult = {
  data?: WatsonxData;
};

export function extractTextFromResult(
  result: Record<string, unknown> | null | undefined,
): string {
  if (!result) return "";

  const wxResult = result as WatsonxResult;
  const content = wxResult.data?.message?.content;

  if (Array.isArray(content)) {
    const parts = content
      .filter(
        (item) =>
          (item.type === "text" || item.response_type === "text") &&
          typeof item.text === "string",
      )
      .map((item) => item.text as string);
    if (parts.length > 0) return parts.join("\n");
  }

  return "";
}

export function extractToolTraces(
  result: Record<string, unknown> | null | undefined,
): ToolTrace[] {
  if (!result) return [];

  const wxResult = result as WatsonxResult;
  const stepHistory = wxResult.data?.message?.step_history;

  if (!Array.isArray(stepHistory)) return [];

  const traces: ToolTrace[] = [];

  for (const step of stepHistory) {
    const stepDetails = step.step_details;
    if (!Array.isArray(stepDetails)) continue;

    for (const detail of stepDetails) {
      if (detail.tool_use) {
        traces.push({
          toolName: String(detail.tool_use.name ?? ""),
          input: detail.tool_use.input,
          output: detail.tool_result?.output,
        });
      }
    }
  }

  return traces;
}

export function extractThreadId(
  providerData: Record<string, unknown> | null | undefined,
): string | null {
  if (!providerData) return null;

  if (typeof providerData.thread_id === "string" && providerData.thread_id) {
    return providerData.thread_id;
  }

  const wxResult = providerData.result as WatsonxResult | undefined;
  const msg = wxResult?.data?.message;

  // thread_id directly on message
  if (typeof msg?.thread_id === "string" && msg.thread_id) {
    return msg.thread_id;
  }

  // thread_id in message.context (watsonx: wxo_thread_id)
  const contextThreadId = msg?.context?.wxo_thread_id;
  if (typeof contextThreadId === "string" && contextThreadId) {
    return contextThreadId;
  }

  if (
    typeof wxResult?.data?.thread_id === "string" &&
    wxResult.data.thread_id
  ) {
    return wxResult.data.thread_id;
  }

  return null;
}
