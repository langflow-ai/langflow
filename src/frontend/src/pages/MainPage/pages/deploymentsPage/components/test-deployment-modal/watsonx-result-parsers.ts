import type { ToolTrace } from "./types";

export type WatsonxContentItem = {
  type?: string;
  response_type?: string;
  text?: string;
};

/**
 * A single step_detail entry inside a step_history step.
 * WxO uses several `type` discriminators:
 *
 * - `"tool_calls"` — the agent decided to invoke one or more tools.
 *     Contains `tool_calls[]` and `agent_display_name`.
 * - `"tool_response"` — the result returned by a tool.
 *     Contains `name`, `content`, and `tool_call_id`.
 * - `"tool_call"` — a mirror/echo of the original call (can be ignored
 *     for display since the info already exists in the `tool_calls` step).
 */
type StepDetail = {
  type?: string;
  // "tool_calls" type
  tool_calls?: Array<{
    id?: string;
    args?: Record<string, unknown>;
    name?: string;
  }>;
  agent_display_name?: string;
  // "tool_response" type
  name?: string;
  content?: unknown;
  tool_call_id?: string;
  // legacy fields (kept for backwards compat)
  tool_use?: { name: string; input: unknown };
  tool_result?: { output: unknown };
};

export type WatsonxMessage = {
  content?: WatsonxContentItem[];
  context?: { wxo_thread_id?: string };
  thread_id?: string;
  step_history?: Array<{
    role?: string;
    step_details?: StepDetail[];
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

  // First pass: collect all tool calls keyed by their id
  const callMap = new Map<
    string,
    { toolName: string; input: unknown; agentName?: string }
  >();

  // Second pass: collect tool responses keyed by tool_call_id
  const responseMap = new Map<string, unknown>();

  for (const step of stepHistory) {
    const stepDetails = step.step_details;
    if (!Array.isArray(stepDetails)) continue;

    for (const detail of stepDetails) {
      // New WxO format: type === "tool_calls"
      if (detail.type === "tool_calls" && Array.isArray(detail.tool_calls)) {
        for (const call of detail.tool_calls) {
          if (call.id) {
            callMap.set(call.id, {
              toolName: call.name ?? "unknown",
              input: call.args,
              agentName: detail.agent_display_name,
            });
          }
        }
      }

      // New WxO format: type === "tool_response"
      if (detail.type === "tool_response" && detail.tool_call_id) {
        responseMap.set(detail.tool_call_id, detail.content);
      }

      // Legacy format (tool_use / tool_result)
      if (detail.tool_use) {
        const legacyId = `legacy-${callMap.size}`;
        callMap.set(legacyId, {
          toolName: String(detail.tool_use.name ?? ""),
          input: detail.tool_use.input,
        });
        if (detail.tool_result) {
          responseMap.set(legacyId, detail.tool_result.output);
        }
      }
    }
  }

  // Merge calls with their responses
  const traces: ToolTrace[] = [];
  callMap.forEach((call, callId) => {
    traces.push({
      toolName: call.toolName,
      input: call.input,
      output: responseMap.get(callId),
      agentName: call.agentName,
    });
  });

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
