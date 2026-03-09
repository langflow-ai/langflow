import { useMemo } from "react";
import { useGetFlowVersions } from "@/controllers/API/queries/flow-version";
import { CURRENT_DRAFT_ID } from "@/pages/FlowPage/components/flowSidebarComponent/components/FlowHistorySidebar/constants";

export type ToolbarDeploymentState =
  | "loading"
  | "deployed"
  | "changes_not_deployed"
  | "not_deployed";

type UseFlowDeploymentStatusArgs = {
  flowId?: string;
  selectedEntryId?: string | null;
};

export function useFlowDeploymentStatus({
  flowId,
  selectedEntryId,
}: UseFlowDeploymentStatusArgs) {
  const { data: historyResponse, isLoading: isLoadingHistory } =
    useGetFlowVersions({ flowId: flowId ?? "" }, { enabled: Boolean(flowId) });

  const history = historyResponse?.entries ?? [];
  const latestHistoryId = history[0]?.id ?? null;
  const selectedHistoryId =
    selectedEntryId && selectedEntryId !== CURRENT_DRAFT_ID
      ? selectedEntryId
      : null;
  const deploymentCountsByHistoryId = historyResponse?.deployment_counts ?? {};

  const hasAnyDeployedHistory = useMemo(
    () => Object.values(deploymentCountsByHistoryId).some((count) => count > 0),
    [deploymentCountsByHistoryId],
  );

  const selectedHistoryDeploymentCount = selectedHistoryId
    ? (deploymentCountsByHistoryId[selectedHistoryId] ?? 0)
    : 0;
  const latestHistoryDeploymentCount = latestHistoryId
    ? (deploymentCountsByHistoryId[latestHistoryId] ?? 0)
    : 0;

  const toolbarStatus: ToolbarDeploymentState = useMemo(() => {
    if (isLoadingHistory) {
      return "loading";
    }
    if (!hasAnyDeployedHistory) {
      return "not_deployed";
    }
    if (selectedHistoryId) {
      return selectedHistoryDeploymentCount > 0 ? "deployed" : "not_deployed";
    }
    return latestHistoryDeploymentCount > 0
      ? "deployed"
      : "changes_not_deployed";
  }, [
    hasAnyDeployedHistory,
    isLoadingHistory,
    latestHistoryDeploymentCount,
    selectedHistoryDeploymentCount,
    selectedHistoryId,
  ]);

  return {
    history,
    deploymentCountsByHistoryId,
    hasAnyDeployedHistory,
    selectedHistoryDeploymentCount,
    latestHistoryDeploymentCount,
    toolbarStatus,
    isLoadingStatus: isLoadingHistory,
  };
}
