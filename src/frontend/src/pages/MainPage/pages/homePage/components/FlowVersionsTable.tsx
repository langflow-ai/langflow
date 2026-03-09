import { useCallback, useEffect, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import ExportModal from "@/modals/exportModal";
import FlowSettingsModal from "@/modals/flowSettingsModal";
import useAlertStore from "@/stores/alertStore";
import type { FlowType } from "@/types/flow";
import type { FlowVersionEntry } from "@/types/flow/version";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import DropdownComponent from "../../../components/dropdown";
import { timeElapsed } from "../../../utils/time-elapse";

type FlowHistoryApiResponse = {
  entries: FlowVersionEntry[];
  deployment_counts?: Record<string, number>;
};

type FlowVersionsTableProps = {
  flows: FlowType[];
  folderId?: string;
};

export default function FlowVersionsTable({
  flows,
  folderId,
}: FlowVersionsTableProps) {
  const navigate = useCustomNavigate();
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
        const response = await api.get<FlowHistoryApiResponse>(
          `${getURL("FLOWS")}/${flowId}/versions/`,
          { params: { limit: 20, offset: 0 } },
        );
        setHistoryByFlowId((prev) => ({ ...prev, [flowId]: response.data }));
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
      <div className="grid grid-cols-[34px_2.4fr_1fr_1fr_1.2fr_30px] items-center px-4 py-4 text-xs font-medium text-muted-foreground">
        <span className="flex justify-center">
          <span className="h-4 w-4 rounded-sm border border-border/70" />
        </span>
        <span>Name</span>
        <span>Version</span>
        <span>Status</span>
        <span>Last updated</span>
        <span className="flex justify-center">
          <ForwardedIconComponent name="EllipsisVertical" className="h-4 w-4" />
        </span>
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
          }) => {
            const isExpanded = expandedFlowIds.has(flow.id);
            const flowStatus = deployedEntryCount > 0 ? "Deployed" : "Draft";
            const swatchIndex =
              (flow.gradient && !isNaN(parseInt(flow.gradient))
                ? parseInt(flow.gradient)
                : getNumberFromString(flow.gradient ?? flow.id)) %
              swatchColors.length;

            return (
              <div
                key={flow.id}
                className="border-b border-border/60 last:border-b-0"
              >
                <div
                  className="grid w-full grid-cols-[34px_2.4fr_1fr_1fr_1.2fr_30px] items-center px-4 py-5 text-left transition-colors hover:bg-muted/20"
                  onClick={() => {
                    navigate(
                      `/flow/${flow.id}${folderId ? `/folder/${folderId}` : ""}`,
                    );
                  }}
                >
                  <span className="flex justify-center">
                    <span className="h-4 w-4 rounded-sm border border-border/70 bg-background" />
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "rounded p-0.5 text-muted-foreground cursor-pointer",
                        hasLoadedHistory && versionCount === 0 && "opacity-40",
                      )}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (hasLoadedHistory && versionCount === 0) return;
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
                      role="button"
                      tabIndex={0}
                    >
                      <ForwardedIconComponent
                        name={isExpanded ? "ChevronDown" : "ChevronRight"}
                        className="h-4 w-4"
                      />
                    </span>
                    <span
                      className={cn(
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-md p-1.5",
                        swatchColors[swatchIndex],
                      )}
                    >
                      <ForwardedIconComponent
                        name={flow.icon ?? "Workflow"}
                        className="h-4 w-4"
                      />
                    </span>
                    <span className="truncate text-sm font-medium">
                      {flow.name}
                    </span>
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {hasLoadedHistory &&
                    versionCount !== null &&
                    versionCount > 0
                      ? `${versionCount} versions`
                      : "-"}
                  </span>
                  <span
                    className={cn(
                      "inline-flex w-fit items-center gap-1 text-sm font-medium",
                      flowStatus === "Deployed"
                        ? "text-foreground"
                        : "text-muted-foreground",
                    )}
                  >
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full",
                        flowStatus === "Deployed"
                          ? "bg-emerald-500"
                          : "bg-muted-foreground/60",
                      )}
                    />
                    {flowStatus}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {timeElapsed(flow.updated_at)} ago
                  </span>
                  <span className="flex justify-center">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="iconSm"
                          className="h-7 w-7 text-muted-foreground hover:text-foreground"
                          onClick={(event) => {
                            event.stopPropagation();
                          }}
                        >
                          <ForwardedIconComponent
                            name="EllipsisVertical"
                            className="h-4 w-4"
                          />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent
                        className="w-[185px]"
                        sideOffset={5}
                        side="bottom"
                        align="end"
                        onClick={(event) => {
                          event.stopPropagation();
                        }}
                      >
                        <DropdownComponent
                          flowData={flow}
                          setOpenDelete={(open) => {
                            setActionFlow(flow);
                            setOpenDelete(open);
                          }}
                          handleExport={() => {
                            setActionFlow(flow);
                            setOpenExportModal(true);
                          }}
                          handleEdit={() => {
                            setActionFlow(flow);
                            setOpenSettings(true);
                          }}
                        />
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </span>
                </div>

                {isExpanded && !hasLoadedHistory && isLoadingHistory && (
                  <div className="grid grid-cols-[34px_2.4fr_1fr_1fr_1.2fr_30px] items-center border-t border-border/50 px-4 py-5 text-sm text-muted-foreground">
                    <span />
                    <span className="pl-11">Loading versions...</span>
                    <span>-</span>
                    <span>-</span>
                    <span>-</span>
                    <span />
                  </div>
                )}
                {isExpanded &&
                  entries.map((entry) => {
                    const isDeployed = (deploymentCounts[entry.id] ?? 0) > 0;
                    return (
                      <div
                        key={entry.id}
                        className="grid cursor-pointer grid-cols-[34px_2.4fr_1fr_1fr_1.2fr_30px] items-center border-t border-border/50 px-4 py-5 text-sm transition-colors hover:bg-muted/20"
                        onClick={() => {
                          const targetPath = `/flow/${flow.id}${folderId ? `/folder/${folderId}` : ""}`;
                          navigate(
                            `${targetPath}?versionId=${encodeURIComponent(entry.id)}`,
                          );
                        }}
                      >
                        <span className="flex justify-center">
                          <span className="h-4 w-4 rounded-sm border border-border/60 bg-background/20" />
                        </span>
                        <div className="flex items-center gap-2 pl-11 text-muted-foreground">
                          <span
                            className={cn(
                              "flex h-6 w-6 shrink-0 items-center justify-center rounded p-1",
                              swatchColors[swatchIndex],
                            )}
                          >
                            <ForwardedIconComponent
                              name={flow.icon ?? "Workflow"}
                              className="h-3.5 w-3.5"
                            />
                          </span>
                          <span className="truncate">
                            {entry.description?.trim()
                              ? entry.description
                              : flow.name}
                          </span>
                        </div>
                        <span>{entry.version_tag}</span>
                        <span
                          className={cn(
                            "inline-flex w-fit items-center gap-1 text-sm font-medium",
                            isDeployed
                              ? "text-foreground"
                              : "text-muted-foreground",
                          )}
                        >
                          <span
                            className={cn(
                              "h-2 w-2 rounded-full",
                              isDeployed
                                ? "bg-emerald-500"
                                : "bg-muted-foreground/60",
                            )}
                          />
                          {isDeployed ? "Deployed" : "Draft"}
                        </span>
                        <span className="text-muted-foreground">
                          {timeElapsed(entry.created_at)} ago
                        </span>
                        <span className="flex justify-center">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="iconSm"
                                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                                onClick={(event) => {
                                  event.stopPropagation();
                                }}
                              >
                                <ForwardedIconComponent
                                  name="EllipsisVertical"
                                  className="h-4 w-4"
                                />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent
                              className="w-[185px]"
                              sideOffset={5}
                              side="bottom"
                              align="end"
                              onClick={(event) => {
                                event.stopPropagation();
                              }}
                            >
                              <DropdownComponent
                                flowData={flow}
                                setOpenDelete={(open) => {
                                  setActionFlow(flow);
                                  setOpenDelete(open);
                                }}
                                handleExport={() => {
                                  setActionFlow(flow);
                                  setOpenExportModal(true);
                                }}
                                handleEdit={() => {
                                  setActionFlow(flow);
                                  setOpenSettings(true);
                                }}
                              />
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </span>
                      </div>
                    );
                  })}
              </div>
            );
          },
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
