import type { VertexDataTypeAPI } from "@/types/api";

export function decisionErrorFromLogs(
  logs: VertexDataTypeAPI["logs"] | undefined,
): string | null {
  return (
    Object.values(logs ?? {})
      .flat()
      .filter((log) => log.name === "Decision evidence")
      .map((log) => decisionErrorMessage(log.message))
      .find((message) => message !== null) ?? null
  );
}

export function decisionErrorMessage(evidence: unknown): string | null {
  if (
    !evidence ||
    typeof evidence !== "object" ||
    !("reason" in evidence) ||
    evidence.reason !== "evaluation_error" ||
    !("activated_branch" in evidence) ||
    evidence.activated_branch !== "default_result" ||
    !("error_action" in evidence) ||
    evidence.error_action !== "Route to Else" ||
    !("error" in evidence) ||
    !evidence.error ||
    typeof evidence.error !== "object" ||
    !("message" in evidence.error)
  ) {
    return null;
  }
  return typeof evidence.error.message === "string"
    ? evidence.error.message
    : null;
}
