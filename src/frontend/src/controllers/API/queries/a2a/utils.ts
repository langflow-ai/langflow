import type { A2ACardOverrides } from "@/types/flow";

// The form mirrors a2a_card_overrides. List fields stay as string arrays (one
// entry per row) so they drive InputListComponent directly. Conversion to/from
// the stored dict lives here so it can be unit-tested without rendering the tab.
export type A2ACardForm = {
  name: string;
  description: string;
  version: string;
  tags: string[];
  examples: string[];
};

const cleanList = (value: string[]): string[] =>
  value.map((entry) => entry.trim()).filter(Boolean);

export const overridesToForm = (
  overrides?: A2ACardOverrides | null,
): A2ACardForm => ({
  name: overrides?.name ?? "",
  description: overrides?.description ?? "",
  version: overrides?.version ?? "",
  tags: overrides?.tags ?? [],
  examples: overrides?.examples ?? [],
});

export const formToOverrides = (form: A2ACardForm): A2ACardOverrides => {
  const overrides: A2ACardOverrides = {};
  if (form.name.trim()) overrides.name = form.name.trim();
  if (form.description.trim()) overrides.description = form.description.trim();
  if (form.version.trim()) overrides.version = form.version.trim();
  const tags = cleanList(form.tags);
  if (tags.length) overrides.tags = tags;
  const examples = cleanList(form.examples);
  if (examples.length) overrides.examples = examples;
  return overrides;
};

// contextId threads a multi-turn conversation (echo back what the server returns);
// taskId resumes an input-required (HITL) task. Both are omitted on a fresh send.
export const buildSendMessageBody = (
  text: string,
  messageId: string,
  opts?: { contextId?: string; taskId?: string },
) => ({
  jsonrpc: "2.0",
  id: 1,
  method: "message/send",
  params: {
    message: {
      role: "user",
      parts: [{ kind: "text", text }],
      messageId,
      ...(opts?.contextId ? { contextId: opts.contextId } : {}),
      ...(opts?.taskId ? { taskId: opts.taskId } : {}),
    },
  },
});

type A2APart = { kind?: string; text?: string };

// Task lifecycle state, serialized as A2A spec strings (verified in test_a2a.py).
export type A2ATaskState =
  | "submitted"
  | "working"
  | "input-required"
  | "completed"
  | "failed"
  | "canceled";

type A2AResult = {
  // Task id (echo back as taskId to resume an input-required task) and the
  // conversation id (echo back as contextId to keep multi-turn memory).
  id?: string;
  contextId?: string;
  artifacts?: { parts?: A2APart[] }[];
  status?: { state?: A2ATaskState; message?: { parts?: A2APart[] } };
  parts?: A2APart[];
};

export type { A2AResult };

// JSON-RPC 2.0 response envelope returned by the A2A endpoint.
export type A2AEnvelope = {
  result?: A2AResult;
  error?: { message?: string };
};

const textFromParts = (parts?: A2APart[]): string[] =>
  (parts ?? [])
    .filter((part) => part?.kind === "text" && part.text)
    .map((part) => part.text as string);

// Extract the reply text from a JSON-RPC result, mirroring the client component's
// call_a2a_agent: a completed task carries artifacts; a paused/failed task carries
// status.message; a bare message carries parts.
export const parseA2AReply = (result?: A2AResult | null): string => {
  if (!result) return "";
  const texts: string[] = [];
  if (Array.isArray(result.artifacts)) {
    for (const artifact of result.artifacts) {
      texts.push(...textFromParts(artifact?.parts));
    }
  }
  if (!texts.length && result.status?.message?.parts) {
    texts.push(...textFromParts(result.status.message.parts));
  }
  if (!texts.length && result.parts) {
    texts.push(...textFromParts(result.parts));
  }
  return texts.join("\n");
};
