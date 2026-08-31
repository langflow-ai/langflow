export type WatsonxFlowEligibilityIssue =
  | "missingChatInput"
  | "multipleChatInputs"
  | "missingChatOutput";

export const WATSONX_ELIGIBILITY_MESSAGE_KEYS: Record<
  WatsonxFlowEligibilityIssue,
  string
> = {
  missingChatInput: "deployments.wxoMissingChatInput",
  multipleChatInputs: "deployments.wxoMultipleChatInputs",
  missingChatOutput: "deployments.wxoMissingChatOutput",
};

export function getWatsonxFlowEligibilityIssue(
  flowData: unknown,
): WatsonxFlowEligibilityIssue | null {
  if (typeof flowData !== "object" || flowData === null) {
    return "missingChatInput";
  }

  const nodesValue = (flowData as { nodes?: unknown }).nodes;
  const nodes = Array.isArray(nodesValue) ? nodesValue : [];
  const nodeTypes = nodes.map((node) =>
    typeof node === "object" && node !== null
      ? (node as { data?: { type?: unknown } }).data?.type
      : undefined,
  );
  const chatInputCount = nodeTypes.filter(
    (nodeType) => nodeType === "ChatInput",
  ).length;
  const chatOutputCount = nodeTypes.filter(
    (nodeType) => nodeType === "ChatOutput",
  ).length;

  if (chatInputCount === 0) return "missingChatInput";
  if (chatInputCount > 1) return "multipleChatInputs";
  if (chatOutputCount === 0) return "missingChatOutput";
  return null;
}
