import { BuildStatus } from "@/constants/enums";
import useFlowStore from "@/stores/flowStore";
import type { NodeDataType } from "@/types/flow";

export const useBuildStatus = (data: NodeDataType, nodeId: string) => {
  const buildStatus = useFlowStore((state) => {
    // Early return if no flow data
    if (!data.node?.flow?.data?.nodes) {
      const status = state.flowBuildStatus[nodeId]?.status;
      console.log(`[useBuildStatus] Node ${nodeId} (simple) -> status:`, status, "from store:", state.flowBuildStatus[nodeId]);
      return status;
    }

    const nodes = data.node.flow.data.nodes;
    const buildStatuses = nodes
      .map((node) => state.flowBuildStatus[node.id]?.status)
      .filter(Boolean);

    // If no build statuses found, return the single node status
    if (buildStatuses.length === 0) {
      const status = state.flowBuildStatus[nodeId]?.status;
      console.log(`[useBuildStatus] Node ${nodeId} (group, no statuses) -> status:`, status);
      return status;
    }

    // Check statuses in order of priority
    if (buildStatuses.every((status) => status === BuildStatus.BUILT)) {
      console.log(`[useBuildStatus] Node ${nodeId} (group) -> BUILT`);
      return BuildStatus.BUILT;
    }
    if (buildStatuses.some((status) => status === BuildStatus.BUILDING)) {
      console.log(`[useBuildStatus] Node ${nodeId} (group) -> BUILDING`);
      return BuildStatus.BUILDING;
    }
    if (buildStatuses.some((status) => status === BuildStatus.ERROR)) {
      console.log(`[useBuildStatus] Node ${nodeId} (group) -> ERROR`);
      return BuildStatus.ERROR;
    }

    console.log(`[useBuildStatus] Node ${nodeId} (group) -> TO_BUILD (default)`);
    return BuildStatus.TO_BUILD;
  });

  return buildStatus;
};
