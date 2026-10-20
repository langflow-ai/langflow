import useVersionPreviewStore from "@/stores/versionPreviewStore";
import type { FlowOperation } from "@/utils/flow-operations/apply";
import { fixesForEdges } from "@/utils/flow-operations/edge-fixes";

/** One violation in a refused write's 422, as the server reports it. */
export type GraphViolation = {
  code: string;
  message: string;
  resolution: "auto" | "manual";
  edge_id?: string;
};

/**
 * The violations a restore was refused for, when every one of them is manual
 * (an edge naming an output the flow's nodes no longer have), or null for any
 * other failure.
 */
// biome-ignore lint/suspicious/noExplicitAny: axios error shape
export function manualViolations(err: any): GraphViolation[] | null {
  const detail = err?.response?.data?.detail;
  if (err?.response?.status !== 422 || detail?.code !== "FLOW_GRAPH_INVALID")
    return null;
  const violations: GraphViolation[] = detail.violations ?? [];
  return violations.length > 0 &&
    violations.every((violation) => violation.resolution === "manual")
    ? violations
    : null;
}

/**
 * The fixes the preview made for the edges `violations` name: what a refused
 * restore is resent with (see edge-fixes). Empty when the preview fixed none.
 */
export function previewFixesFor(violations: GraphViolation[]): FlowOperation[] {
  return fixesForEdges(
    useVersionPreviewStore.getState().previewFixes,
    new Set(violations.map((violation) => violation.edge_id ?? "")),
  );
}
