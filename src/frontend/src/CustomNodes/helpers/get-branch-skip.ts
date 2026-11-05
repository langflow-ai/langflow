import type { AllNodeType, EdgeType } from "@/types/flow";
import type { FlowStoreType } from "@/types/zustand/flow";

export type BranchSkip = {
  /** Display name of the branch component that routed away from the node. */
  component: string;
  /** Display names of the outputs that branch component sent the input to. */
  outputs: string[];
};

/**
 * Explain why a node on a branch was not run: which branch component skipped
 * it and which of that component's outputs received the input instead.
 */
export function getBranchSkip(
  nodeId: string,
  flowBuildStatus: FlowStoreType["flowBuildStatus"],
  nodes: AllNodeType[],
  edges: EdgeType[],
): BranchSkip | null {
  const branchId = flowBuildStatus[nodeId]?.skippedBy;
  if (!branchId) return null;
  const branchNode = nodes.find((node) => node.id === branchId)?.data.node;
  if (!branchNode) return null;

  const skippedOutputs = new Set(
    edges
      .filter(
        (edge) =>
          edge.source === branchId &&
          flowBuildStatus[edge.target]?.skippedBy === branchId,
      )
      .map((edge) => edge.data?.sourceHandle?.name),
  );
  const outputs = (branchNode.outputs ?? [])
    .filter((output) => !skippedOutputs.has(output.name))
    .map((output) => output.display_name ?? output.name);

  return { component: branchNode.display_name, outputs };
}
