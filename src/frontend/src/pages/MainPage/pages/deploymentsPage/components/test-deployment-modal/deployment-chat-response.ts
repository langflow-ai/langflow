import type { DeploymentRunProviderData } from "@/controllers/API/queries/deployments/use-post-deployment-run";
import type { ChatMessage } from "./types";
import {
  extractTextFromResult,
  extractToolTraces,
} from "./watsonx-result-parsers";

const TERMINAL_STATUSES = new Set([
  "completed",
  "success",
  "failed",
  "error",
  "cancelled",
]);

export type AssistantMessageUpdate = Partial<
  Pick<ChatMessage, "content" | "toolTraces" | "isLoading" | "error">
>;

export function isTerminalStatus(status: string | null | undefined): boolean {
  return !!status && TERMINAL_STATUSES.has(status.toLowerCase());
}

export function buildAssistantSuccessUpdate(
  providerData: DeploymentRunProviderData | null | undefined,
): AssistantMessageUpdate {
  const result = providerData?.result;
  const replyText =
    extractTextFromResult(result) ||
    (typeof providerData?.status === "string" ? providerData.status : "Done.");
  const toolTraces = extractToolTraces(result);

  return {
    content: replyText,
    toolTraces: toolTraces.length > 0 ? toolTraces : undefined,
    isLoading: false,
  };
}

export function buildAssistantErrorUpdate(
  error: string,
): AssistantMessageUpdate {
  return {
    content: "",
    isLoading: false,
    error,
  };
}
