import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import {
  useGetDeploymentProviders,
  useGetDeployments,
} from "@/controllers/API/queries/deployments/use-deployments";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import ExportModal from "@/modals/exportModal";
import FlowSettingsModal from "@/modals/flowSettingsModal";
import useAlertStore from "@/stores/alertStore";
import type { FlowType } from "@/types/flow";
import type { FlowHistoryEntry } from "@/types/flow/history";
import { cn } from "@/utils/utils";
import FlowVersionsTableRow from "./FlowVersionsTableRow";

type FlowHistoryApiResponse = {
  entries: FlowHistoryEntry[];
  deployment_counts?: Record<string, number>;
};

type FlowVersionApiResponse = {
  entries: FlowHistoryEntry[];
};

type MatchedDeployment = {
  id: string;
  name: string;
  type: string;
  mode?: string;
};

type FlowVersionsTableProps = {
  flows: FlowType[];
  folderId?: string;
};

export default function FlowVersionsTable({
  flows,
  folderId,
}: FlowVersionsTableProps) {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { deleteFlow } = useDeleteFlow();
  const [actionFlow, setActionFlow] = useState<FlowType | null>(null);
  const [openDelete, setOpenDelete] = useState(false);
  const [openExportModal, setOpenExportModal] = useState(false);
  const [openSettings, setOpenSettings] = useState(false);
  const [expandedFlowIds, setExpandedFlowIds] = useState<Set<string>>(
    new Set(),
  );
  const [historyByFlowId, setHistoryByFlowId] = useState<
    Record<string, FlowHistoryApiResponse>
  >({});
  const [isLoadingHistoryByFlowId, setIsLoadingHistoryByFlowId] = useState<
    Record<string, boolean>
  >({});
  const expandedHistoryIds = useMemo(() => {
    return Array.from(expandedFlowIds).flatMap((flowId) => {
      return (historyByFlowId[flowId]?.entries ?? []).map((entry) => entry.id);
    });
  }, [expandedFlowIds, historyByFlowId]);
  const shouldLoadDeploymentMatches = expandedHistoryIds.length > 0;

  const providersQuery = useGetDeploymentProviders({
    enabled: shouldLoadDeploymentMatches,
    refetchOnWindowFocus: false,
  });
  const activeProviderId = providersQuery.data?.providers?.[0]?.id ?? "";

  const deploymentsQuery = useGetDeployments(
    {
      providerId: activeProviderId,
      page: 1,
      pageSize: 100,
      historyIds: expandedHistoryIds,
      matchLimit: 100,
    },
    {
      enabled: shouldLoadDeploymentMatches && Boolean(activeProviderId),
      refetchOnWindowFocus: false,
    },
  );

  const deploymentMatchesByHistoryId = useMemo<
    Record<string, MatchedDeployment[]>
  >(() => {
    const acc: Record<string, MatchedDeployment[]> = {};
    for (const deployment of deploymentsQuery.data?.deployments ?? []) {
      const matchedIds = Array.isArray(
        deployment.provider_data?.matched_history_ids,
      )
        ? deployment.provider_data.matched_history_ids
        : [];
      if (matchedIds.length === 0) {
        continue;
      }
      const item: MatchedDeployment = {
        id: deployment.id,
        name: deployment.name,
        type: deployment.type,
        mode:
          typeof deployment.provider_data?.mode === "string"
            ? deployment.provider_data.mode
            : undefined,
      };
      for (const historyId of matchedIds) {
        if (!historyId) continue;
        if (!acc[historyId]) {
          acc[historyId] = [];
        }
        acc[historyId].push(item);
      }
    }
    return acc;
  }, [deploymentsQuery.data?.deployments]);

  useEffect(() => {
    const flowIds = new Set(flows.map((flow) => flow.id));
    setHistoryByFlowId((prev) =>
      Object.fromEntries(
        Object.entries(prev).filter(([flowId]) => flowIds.has(flowId)),
      ),
    );
    setIsLoadingHistoryByFlowId((prev) =>
      Object.fromEntries(
        Object.entries(prev).filter(([flowId]) => flowIds.has(flowId)),
      ),
    );
  }, [flows]);

  const loadHistoryForFlow = useCallback(
    async (flowId: string) => {
      if (historyByFlowId[flowId] || isLoadingHistoryByFlowId[flowId]) {
        return;
      }
      setIsLoadingHistoryByFlowId((prev) => ({ ...prev, [flowId]: true }));
      try {
        try {
          const response = await api.get<FlowHistoryApiResponse>(
            `${getURL("FLOWS")}/${flowId}/history/`,
            { params: { limit: 20, offset: 0 } },
          );
          setHistoryByFlowId((prev) => ({ ...prev, [flowId]: response.data }));
        } catch {
          const fallbackResponse = await api.get<FlowVersionApiResponse>(
            `${getURL("FLOWS")}/${flowId}/versions/`,
            { params: { limit: 20, offset: 0 } },
          );
          setHistoryByFlowId((prev) => ({
            ...prev,
            [flowId]: {
              entries: fallbackResponse.data.entries ?? [],
              deployment_counts: {},
            },
          }));
        }
      } catch {
        setHistoryByFlowId((prev) => ({
          ...prev,
          [flowId]: { entries: [], deployment_counts: {} },
        }));
      } finally {
        setIsLoadingHistoryByFlowId((prev) => ({ ...prev, [flowId]: false }));
      }
    },
    [historyByFlowId, isLoadingHistoryByFlowId],
  );

  useEffect(() => {
    for (const flow of flows) {
      if (!historyByFlowId[flow.id] && !isLoadingHistoryByFlowId[flow.id]) {
        void loadHistoryForFlow(flow.id);
      }
    }
  }, [flows, historyByFlowId, isLoadingHistoryByFlowId, loadHistoryForFlow]);

  const rows = useMemo(() => {
    return flows.map((flow) => {
      const historyResponse = historyByFlowId[flow.id];
      const hasLoadedHistory = Boolean(historyResponse);
      const entries = historyResponse?.entries ?? [];
      const deploymentCounts = historyResponse?.deployment_counts ?? {};
      const deployedEntryCount = hasLoadedHistory
        ? entries.filter((entry) => (deploymentCounts[entry.id] ?? 0) > 0)
            .length
        : flow.has_deployments
          ? 1
          : 0;
      return {
        flow,
        entries,
        hasLoadedHistory,
        versionCount: hasLoadedHistory ? entries.length : null,
        deployedEntryCount,
        deploymentCounts,
        isLoadingHistory: isLoadingHistoryByFlowId[flow.id] ?? false,
      };
    });
  }, [flows, historyByFlowId, isLoadingHistoryByFlowId]);

  const tableGridCols =
    "grid-cols-[minmax(0,2.4fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.2fr)_2rem]";

  const handleDelete = async () => {
    if (!actionFlow) {
      return;
    }
    try {
      await deleteFlow({ id: [actionFlow.id] });
      setSuccessData({ title: "Flow deleted successfully" });
    } catch {
      setErrorData({
        title: "Error deleting flow",
        list: ["Please try again"],
      });
    }
  };

  return (
    <div className="px-5 pb-5 pt-7">
      <div
        className={cn(
          "grid items-center px-4 py-4 text-xs font-medium text-muted-foreground",
          tableGridCols,
        )}
      >
        <span className="pl-3">Name</span>
        <span>Version</span>
        <span>Status</span>
        <span>Last updated</span>
        <span />
      </div>
      <div className="mt-1 border-y border-border/70">
        {rows.map(
          ({
            flow,
            entries,
            hasLoadedHistory,
            versionCount,
            deployedEntryCount,
            deploymentCounts,
            isLoadingHistory,
          }) => (
            <FlowVersionsTableRow
              key={flow.id}
              flow={flow}
              entries={entries}
              hasLoadedHistory={hasLoadedHistory}
              versionCount={versionCount}
              deployedEntryCount={deployedEntryCount}
              deploymentCounts={deploymentCounts}
              deploymentMatchesByHistoryId={deploymentMatchesByHistoryId}
              isLoadingHistory={isLoadingHistory}
              canExpand={
                hasLoadedHistory && versionCount !== null && versionCount > 1
              }
              folderId={folderId}
              tableGridCols={tableGridCols}
              isExpanded={expandedFlowIds.has(flow.id)}
              onToggleExpand={() => {
                setExpandedFlowIds((prev) => {
                  const shouldOpen = !prev.has(flow.id);
                  const next = new Set(prev);
                  if (next.has(flow.id)) {
                    next.delete(flow.id);
                  } else {
                    next.add(flow.id);
                  }
                  if (shouldOpen && !hasLoadedHistory) {
                    void loadHistoryForFlow(flow.id);
                  }
                  return next;
                });
              }}
              onSetActionFlow={(flow, action) => {
                setActionFlow(flow);
                if (action === "delete") {
                  setOpenDelete(true);
                } else if (action === "export") {
                  setOpenExportModal(true);
                } else if (action === "settings") {
                  setOpenSettings(true);
                }
              }}
            />
          ),
        )}
      </div>
      {actionFlow && (
        <>
          <DeleteConfirmationModal
            open={openDelete}
            setOpen={setOpenDelete}
            onConfirm={() => void handleDelete()}
            description="flow"
            note="and its message history"
          />
          <ExportModal
            open={openExportModal}
            setOpen={setOpenExportModal}
            flowData={actionFlow}
          />
          <FlowSettingsModal
            open={openSettings}
            setOpen={setOpenSettings}
            flowData={actionFlow}
          />
        </>
      )}
    </div>
  );
}
