import type { AllNodeType, EdgeType } from "@/types/flow";

/**
 * ReactFlow's EdgeWrapper reads `edge.ariaLabel` natively and uses it to name
 * the wrapping <g> (a widget role — we set ariaRole="button" — when focusable,
 * role="img", a pruned leaf, otherwise). Setting it here, at build time, is the single source of truth:
 * it replaces RF's raw-id default instead of layering a second, redundant
 * name on the interaction path inside DefaultEdge.
 */
export function getEdgeAriaLabel(
  edge: EdgeType,
  getNode: (id: string) => AllNodeType | undefined,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  const sourceNode = getNode(edge.source);
  const targetNode = getNode(edge.target);
  return t("edge.ariaLabel", {
    source: sourceNode?.data?.node?.display_name ?? edge.source,
    target: targetNode?.data?.node?.display_name ?? edge.target,
  });
}
