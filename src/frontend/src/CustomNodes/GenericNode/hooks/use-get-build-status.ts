import { BuildStatus } from "@/constants/enums";
import useFlowStore from "@/stores/flowStore";
import type { NodeDataType } from "@/types/flow";

export const useBuildStatus = (data: NodeDataType, nodeId: string) => {
  return useFlowStore((state) => {
    // Early return if no flow data
    if (!data.node?.flow?.data?.nodes) {
      return state.flowBuildStatus[nodeId]?.status;
    }

    const nodes = data.node.flow.data.nodes;
    const buildStatuses = nodes
      .map((node) => state.flowBuildStatus[node.id]?.status)
      .filter(Boolean);

    // If no build statuses found, return the single node status
    if (buildStatuses.length === 0) {
      return state.flowBuildStatus[nodeId]?.status;
    }

    // Check statuses in order of priority
    if (buildStatuses.every((status) => status === BuildStatus.BUILT)) {
      return BuildStatus.BUILT;
    }
    if (buildStatuses.some((status) => status === BuildStatus.BUILDING)) {
      return BuildStatus.BUILDING;
    }
    if (buildStatuses.some((status) => status === BuildStatus.ERROR)) {
      return BuildStatus.ERROR;
    }

    return BuildStatus.TO_BUILD;
  });
};
