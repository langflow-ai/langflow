import type { AllNodeType } from "@/types/flow";
import type { FlowStoreType } from "@/types/zustand/flow";

export type BranchSkip = {
  /** Display name of the router that excluded the node. */
  component: string;
  /** Display names of the outputs that router took instead. */
  outputs: string[];
};

/**
 * Explain why a node was not run, from what the backend reported: which router
 * excluded it and which of that router's outputs it took instead.
 */
export function getBranchSkip(
  nodeId: string,
  flowBuildStatus: FlowStoreType["flowBuildStatus"],
  nodes: AllNodeType[],
): BranchSkip | null {
  const entry = flowBuildStatus[nodeId];
  if (!entry?.skippedBy) return null;
  const branchNode = nodes.find((node) => node.id === entry.skippedBy)?.data
    .node;
  if (!branchNode) return null;

  const taken = new Set(entry.takenOutputs ?? []);
  const outputs = (branchNode.outputs ?? [])
    .filter((output) => taken.has(output.name))
    .map((output) => output.display_name || output.name);

  return { component: branchNode.display_name, outputs };
}
