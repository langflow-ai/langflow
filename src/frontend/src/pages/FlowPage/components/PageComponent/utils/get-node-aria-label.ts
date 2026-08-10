import type { AllNodeType } from "@/types/flow";

/**
 * Note nodes don't carry a meaningful component display_name (it's an empty
 * string at runtime, not undefined, so a `??` fallback to node.type never
 * triggers) — branch on the XYFlow node type instead of relying on it.
 */
export function getNodeAriaLabel(
  node: AllNodeType,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  if (node.type === "noteNode") {
    return t("noteNode.ariaLabel");
  }
  return t("flow.nodeAriaLabel", {
    name: node.data?.node?.display_name || node.data?.type,
  });
}
