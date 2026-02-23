import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  useDeleteHistoryEntry,
  useGetFlowHistory,
  useGetFlowHistoryEntry,
  usePostCreateSnapshot,
} from "@/controllers/API/queries/flow-history";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Background,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
} from "@xyflow/react";
import {
  cleanEdges,
  downloadFlow,
  processFlowEdges,
  processFlowNodes,
  removeApiKeys,
  updateEdges,
} from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import { cloneDeep } from "lodash";
import { ErrorBoundary } from "react-error-boundary";
import { nodeTypes, edgeTypes } from "../../consts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Read-only canvas preview (uses real Langflow node types)
// ---------------------------------------------------------------------------

function PreviewCanvas({ nodes, edges }: { nodes: any[]; edges: any[] }) {
  // Defer edges until nodes have been measured and handle bounds are known.
  const nodesInitialized = useNodesInitialized();

  return (
    <ReactFlow
      nodes={nodes}
      edges={nodesInitialized ? edges : []}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      nodesDraggable={false}
      nodesConnectable={false}
      nodesFocusable={false}
      edgesFocusable={false}
      elementsSelectable={false}
      panOnDrag={true}
      zoomOnScroll={true}
      fitView
      fitViewOptions={{ padding: 0.2, minZoom: 0.25, maxZoom: 2 }}
      proOptions={{ hideAttribution: true }}
    >
      <Background size={2} gap={20} />
    </ReactFlow>
  );
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CURRENT_DRAFT_ID = "__current_draft__";

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------

interface FlowHistoryPanelProps {
  flowId: string;
  onClose: () => void;
}

export default function FlowHistoryPanel({
  flowId,
  onClose,
}: FlowHistoryPanelProps) {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const applyFlowToCanvas = useApplyFlowToCanvas();

  const [description, setDescription] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedId, setSelectedId] = useState<string>(CURRENT_DRAFT_ID);
  const [deleteTarget, setDeleteTarget] = useState<{
    id: string;
    versionTag: string;
  } | null>(null);
  const [restoreConfirm, setRestoreConfirm] = useState<{
    historyId: string;
    versionTag: string;
  } | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);
  const [saveDraftOnRestore, setSaveDraftOnRestore] = useState(true);
  const [pruneWarning, setPruneWarning] = useState(false);

  const {
    data: historyResponse,
    isLoading,
    isError: isListError,
  } = useGetFlowHistory({ flowId }, { refetchInterval: 10000 });

  const history = historyResponse?.entries;
  const maxEntries = historyResponse?.max_entries;

  const { mutate: createSnapshot, isPending: isCreating } =
    usePostCreateSnapshot();
  const { mutate: deleteEntry, isPending: isDeleting } =
    useDeleteHistoryEntry();

  // Declarative query for the selected history entry's full data
  const selectedHistoryId = selectedId !== CURRENT_DRAFT_ID ? selectedId : "";
  const {
    data: selectedEntryFull,
    isLoading: isLoadingEntry,
    isError: isEntryError,
  } = useGetFlowHistoryEntry(
    { flowId, historyId: selectedHistoryId },
    { enabled: !!selectedHistoryId, gcTime: 0, staleTime: 0 },
  );

  const currentFlow = useFlowStore((state) => state.currentFlow);

  // Capture the original store state when the panel mounts so we can
  // restore it when the panel closes or the user switches to "Current Draft".
  const originalStoreRef = useRef({
    nodes: cloneDeep(useFlowStore.getState().nodes),
    edges: cloneDeep(useFlowStore.getState().edges),
  });

  // NOTE: Auto-save disabling and inspection panel hiding are managed by the
  // parent HistoryButton component. This ensures cleanup runs even if this
  // component crashes during render.

  // Process historical data through the same pipeline the main canvas uses
  // (processFlowEdges → processFlowNodes → updateEdges → cleanEdges).
  const processedPreview = useMemo(() => {
    if (selectedId === CURRENT_DRAFT_ID || !selectedEntryFull?.data)
      return null;

    try {
      const cloned = cloneDeep(selectedEntryFull.data);
      const flow = { data: cloned } as any;
      processFlowEdges(flow);
      processFlowNodes(flow);
      updateEdges(cloned.edges);
      const { edges: cleaned } = cleanEdges(cloned.nodes, cloned.edges);
      return { nodes: cloned.nodes, edges: cleaned };
    } catch (err) {
      console.error("Failed to process historical flow data for preview:", err);
      return { nodes: [], edges: [], error: true };
    }
  }, [selectedId, selectedEntryFull?.data]);

  // Sync the global flow store with whatever version is being previewed.
  // GenericNode and its sub-components read edges/nodes from the store, so
  // this ensures handle visibility and connection state match the preview.
  useLayoutEffect(() => {
    if (processedPreview) {
      useFlowStore.setState({
        nodes: processedPreview.nodes,
        edges: processedPreview.edges,
      });
    } else {
      useFlowStore.setState({
        nodes: originalStoreRef.current.nodes,
        edges: originalStoreRef.current.edges,
      });
    }
  }, [processedPreview]);

  // Restore the original store state when the panel unmounts.
  useEffect(() => {
    return () => {
      useFlowStore.setState({
        nodes: originalStoreRef.current.nodes,
        edges: originalStoreRef.current.edges,
      });
    };
  }, []);

  // Escape key closes the panel (or dismiss restore/delete/prune prompts)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (pruneWarning) {
          setPruneWarning(false);
        } else if (deleteTarget) {
          setDeleteTarget(null);
        } else if (restoreConfirm) {
          setRestoreConfirm(null);
        } else {
          onClose();
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose, restoreConfirm, deleteTarget, pruneWarning]);

  // The nodes/edges shown in the preview canvas
  const previewData = useMemo(() => {
    if (selectedId === CURRENT_DRAFT_ID) {
      return {
        nodes: originalStoreRef.current.nodes,
        edges: originalStoreRef.current.edges,
      };
    }
    return processedPreview ?? { nodes: [], edges: [] };
  }, [selectedId, processedPreview]);

  // Select a history entry — data is fetched by useGetFlowHistoryEntry hook
  const handleSelectEntry = useCallback((entryId: string) => {
    setSelectedId(entryId);
  }, []);

  const doCreateSnapshot = useCallback(() => {
    createSnapshot(
      { flowId, description: description || null },
      {
        onSuccess: () => {
          setSuccessData({ title: "Version saved" });
          setDescription("");
          setShowCreateForm(false);
          setPruneWarning(false);
        },
        onError: (err: any) => {
          const detail = err?.response?.data?.detail;
          setErrorData({
            title: "Failed to save version",
            ...(detail ? { list: [detail] } : {}),
          });
          setPruneWarning(false);
        },
      },
    );
  }, [flowId, description, createSnapshot, setSuccessData, setErrorData]);

  const handleCreateSnapshot = useCallback(() => {
    if (history && maxEntries && history.length >= maxEntries) {
      setPruneWarning(true);
      return;
    }
    doCreateSnapshot();
  }, [history, maxEntries, doCreateSnapshot]);

  // Restore = call the /activate endpoint (which auto-snapshots server-side
  // and returns the updated flow).
  // Accepts historyId explicitly so the restore target can't drift if the
  // user somehow changes the selection while the dialog is open.
  const doRestore = useCallback(
    async (historyId: string) => {
      setIsRestoring(true);
      let updatedFlow: any;
      try {
        const response = await api.post(
          `${getURL("FLOWS")}/${flowId}/history/${historyId}/activate`,
          null,
          { params: { save_draft: saveDraftOnRestore } },
        );
        updatedFlow = response.data;
      } catch (err: any) {
        // API call failed — server state is unchanged
        const detail = err?.response?.data?.detail;
        setErrorData({
          title: "Failed to restore version",
          ...(detail ? { list: [detail] } : {}),
        });
        setIsRestoring(false);
        setRestoreConfirm(null);
        return;
      }

      try {
        // Apply through the same shared pipeline as normal flow loading:
        // processFlows → setCurrentFlow (→ resetFlow) → refreshAllModelInputs
        applyFlowToCanvas(updatedFlow);

        // Update the ref so the unmount cleanup restores the new data,
        // not the pre-restore data.
        originalStoreRef.current = {
          nodes: useFlowStore.getState().nodes,
          edges: useFlowStore.getState().edges,
        };

        setSuccessData({ title: "Version restored" });

        // Fit the canvas to the restored flow after React re-renders the new
        // nodes. This mirrors what happens on initial flow load (fitView prop).
        requestAnimationFrame(() => {
          useFlowStore.getState().reactFlowInstance?.fitView({
            padding: 0.2,
            minZoom: 0.25,
            maxZoom: 2,
          });
        });
      } catch {
        // Server committed the change but client rendering failed
        setErrorData({
          title:
            "Version restored on server, but there was an issue rendering it. Please refresh the page.",
        });
      } finally {
        // Close the history panel and return to the main editor
        onClose();
        setIsRestoring(false);
        setRestoreConfirm(null);
      }
    },
    [flowId, saveDraftOnRestore, applyFlowToCanvas, setSuccessData, setErrorData, onClose],
  );

  const handleDelete = useCallback(
    (historyId: string) => {
      deleteEntry(
        { flowId, historyId },
        {
          onSuccess: () => {
            setSuccessData({ title: "Version deleted" });
            setDeleteTarget(null);
            if (selectedId === historyId) {
              setSelectedId(CURRENT_DRAFT_ID);
            }
          },
          onError: (err: any) => {
            const detail = err?.response?.data?.detail;
            setErrorData({
              title: "Failed to delete version",
              ...(detail ? { list: [detail] } : {}),
            });
            setDeleteTarget(null);
          },
        },
      );
    },
    [flowId, selectedId, deleteEntry, setSuccessData, setErrorData],
  );

  const handleExportEntry = useCallback(
    async (entryId: string) => {
      try {
        let data: any;
        let tag: string;

        if (entryId === CURRENT_DRAFT_ID) {
          data = currentFlow?.data;
          tag = "draft";
        } else {
          // Fetch directly — avoids timing issues with the shared query hook
          const response = await api.get(
            `${getURL("FLOWS")}/${flowId}/history/${entryId}`,
          );
          data = response.data?.data;
          tag = response.data?.version_tag ?? "version";
        }

        if (!data) {
          setErrorData({ title: "No data available to export" });
          return;
        }

        const flowName = `${currentFlow?.name || "flow"}_${tag}`;
        const flowToExport = removeApiKeys({
          id: currentFlow?.id ?? "",
          data,
          name: flowName,
          description: currentFlow?.description ?? "",
          is_component: false,
        } as any);

        await downloadFlow(flowToExport, flowName, flowToExport.description);
      } catch (err: any) {
        const detail = err?.response?.data?.detail;
        setErrorData({
          title: "Failed to export version",
          ...(detail ? { list: [detail] } : {}),
        });
      }
    },
    [flowId, currentFlow, setErrorData],
  );

  const selectedHistoryEntry = history?.find((e) => e.id === selectedId);
  const isViewingDraft = selectedId === CURRENT_DRAFT_ID;

  // Container ref for dropdown portals — keeps them inside this panel's
  // stacking context instead of competing at document.body.
  const panelRef = useRef<HTMLDivElement>(null);

  return (
    <div ref={panelRef} className="fixed inset-0 z-100 flex bg-background">
      {/* Main preview area */}
      <div className="flex flex-1 flex-col">
        {/* Top bar */}
        <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-2">
          <div className="flex items-center gap-3">
            {isViewingDraft ? (
              <span className="text-sm font-medium">Current Draft</span>
            ) : selectedHistoryEntry ? (
              <>
                <span className="text-sm font-medium">
                  {selectedHistoryEntry.version_tag}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatTimestamp(selectedHistoryEntry.created_at)}
                </span>
                {selectedHistoryEntry.description && (
                  <span className="text-sm text-muted-foreground">
                    — {selectedHistoryEntry.description}
                  </span>
                )}
              </>
            ) : (
              <span className="text-sm text-muted-foreground">
                Select a version to preview
              </span>
            )}
          </div>
        </div>

        {/* Canvas preview */}
        <div className="flex-1 bg-muted/20">
          {isEntryError ? (
            <div className="flex h-full items-center justify-center text-destructive">
              Failed to load version data
            </div>
          ) : isLoadingEntry ? (
            <div className="flex h-full items-center justify-center">
              <ForwardedIconComponent
                name="Loader2"
                className="h-6 w-6 animate-spin text-muted-foreground"
              />
            </div>
          ) : (processedPreview as any)?.error ? (
            <div className="flex h-full items-center justify-center text-destructive">
              This version's data could not be rendered for preview
            </div>
          ) : previewData.nodes.length > 0 ? (
            <ErrorBoundary
              FallbackComponent={() => (
                <div className="flex h-full items-center justify-center text-destructive">
                  Failed to render preview
                </div>
              )}
            >
              <ReactFlowProvider>
                <PreviewCanvas
                  nodes={previewData.nodes}
                  edges={previewData.edges}
                />
              </ReactFlowProvider>
            </ErrorBoundary>
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              No data to preview
            </div>
          )}
        </div>
      </div>

      {/* Right sidebar */}
      <div className="flex w-72 flex-col border-l bg-background">
        {/* Sidebar header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-sm font-semibold">Version History</span>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <ForwardedIconComponent name="X" className="h-4 w-4" />
          </Button>
        </div>

        {/* Save Version */}
        <div className="border-b px-3 py-3">
          {showCreateForm ? (
            <div className="flex flex-col gap-2">
              <input
                type="text"
                placeholder="Description (optional)"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="h-8 rounded-md border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreateSnapshot();
                  if (e.key === "Escape") {
                    e.stopPropagation();
                    setShowCreateForm(false);
                  }
                }}
                autoFocus
              />
              <div className="flex gap-2">
                <Button
                  variant="default"
                  size="xs"
                  onClick={handleCreateSnapshot}
                  loading={isCreating}
                  className="flex-1"
                >
                  Save
                </Button>
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => setShowCreateForm(false)}
                  className="flex-1"
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowCreateForm(true)}
              className="w-full"
            >
              <ForwardedIconComponent name="Save" className="h-4 w-4" />
              <span>Save Version</span>
            </Button>
          )}
        </div>

        {/* Version list */}
        <div className="flex-1 overflow-y-auto">
          {/* Current Draft row — always first */}
          <div
            className={cn(
              "flex cursor-pointer items-center gap-3 border-b px-3 py-3 transition-colors hover:bg-accent/40",
              isViewingDraft && "bg-accent/60",
            )}
            onClick={() => handleSelectEntry(CURRENT_DRAFT_ID)}
          >
            <div className="flex w-3 shrink-0 justify-center">
              <div className="h-2.5 w-2.5 rounded-full bg-blue-500" />
            </div>
            <div className="min-w-0 flex-1">
              <span className="text-sm font-medium">Current Draft</span>
              <br />
              <span className="text-xs text-muted-foreground">
                Working version
              </span>
            </div>
          </div>

          {/* History count */}
          {history && history.length > 0 && (
            <div className="border-b px-3 py-2 text-xs text-muted-foreground">
              {history.length}{maxEntries ? ` / ${maxEntries}` : ""} versions
            </div>
          )}

          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <ForwardedIconComponent
                name="Loader2"
                className="h-5 w-5 animate-spin text-muted-foreground"
              />
            </div>
          )}
          {isListError && (
            <div className="px-4 py-6 text-center text-xs text-destructive">
              Failed to load version history
            </div>
          )}
          {!isLoading && !isListError && (!history || history.length === 0) && (
            <div className="px-4 py-6 text-center text-xs text-muted-foreground">
              No saved versions yet
            </div>
          )}
          {history?.map((entry) => {
            const isSelected = entry.id === selectedId;
            return (
              <div
                key={entry.id}
                className={cn(
                  "flex cursor-pointer items-center gap-3 border-b px-3 py-3 transition-colors hover:bg-accent/40",
                  isSelected && "bg-accent/60",
                )}
                onClick={() => handleSelectEntry(entry.id)}
              >
                {/* Spacer for alignment with "Current Draft" dot */}
                <div className="w-3 shrink-0" />

                {/* Version info */}
                <div className="min-w-0 flex-1">
                  <span className="text-sm font-medium">
                    {entry.version_tag}
                  </span>
                  <br />
                  <span className="text-xs text-muted-foreground">
                    {formatTimestamp(entry.created_at)}
                  </span>
                  {entry.description && (
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {entry.description}
                    </p>
                  )}
                </div>

                {/* Three-dot menu */}
                <DropdownMenu>
                  <DropdownMenuTrigger
                    asChild
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectEntry(entry.id);
                    }}
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0"
                    >
                      <ForwardedIconComponent
                        name="MoreVertical"
                        className="h-4 w-4"
                      />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    className="w-44"
                    container={panelRef.current}
                  >
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        setRestoreConfirm({
                          historyId: entry.id,
                          versionTag: entry.version_tag,
                        });
                      }}
                    >
                      <ForwardedIconComponent
                        name="RotateCcw"
                        className="mr-2 h-3.5 w-3.5"
                      />
                      Restore
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        handleExportEntry(entry.id);
                      }}
                    >
                      <ForwardedIconComponent
                        name="Download"
                        className="mr-2 h-3.5 w-3.5"
                      />
                      Export
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget({
                          id: entry.id,
                          versionTag: entry.version_tag,
                        });
                      }}
                      className="text-destructive focus:text-destructive"
                    >
                      <ForwardedIconComponent
                        name="Trash2"
                        className="mr-2 h-3.5 w-3.5"
                      />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            );
          })}
        </div>
      </div>

      {/* Restore confirmation dialog */}
      {restoreConfirm && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/40">
          <div className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg">
            <div className="flex items-center gap-2">
              <ForwardedIconComponent
                name="RotateCcw"
                className="h-5 w-5 text-foreground"
              />
              <span className="text-lg font-semibold">Restore Version</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Restore <strong>{restoreConfirm.versionTag}</strong> as the
              working draft?
            </p>
            <label className="flex items-center gap-2 cursor-pointer">
              <Checkbox
                checked={saveDraftOnRestore}
                onCheckedChange={(checked) =>
                  setSaveDraftOnRestore(checked === true)
                }
              />
              <span className="text-sm">Save current working draft</span>
            </label>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRestoreConfirm(null)}
              >
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => doRestore(restoreConfirm.historyId)}
                loading={isRestoring}
              >
                Restore
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation dialog */}
      {deleteTarget && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/40">
          <div className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg">
            <div className="flex items-center gap-2">
              <ForwardedIconComponent
                name="Trash2"
                className="h-5 w-5 text-destructive"
              />
              <span className="text-lg font-semibold">Delete Version</span>
            </div>
            <p className="text-sm text-muted-foreground">
              This will permanently delete{" "}
              <strong>{deleteTarget.versionTag}</strong>. This can't be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleDelete(deleteTarget.id)}
                loading={isDeleting}
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Prune warning dialog */}
      {pruneWarning && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/40">
          <div className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg">
            <div className="flex items-center gap-2">
              <ForwardedIconComponent
                name="AlertTriangle"
                className="h-5 w-5 text-warning"
              />
              <span className="text-lg font-semibold">
                Version Limit Reached
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              {(() => {
                const pruneCount = (history?.length ?? 0) + 1 - (maxEntries ?? 0);
                if (pruneCount <= 1) {
                  return (
                    <>
                      You've reached the maximum of{" "}
                      <strong>{maxEntries}</strong> saved versions. Saving a
                      new version will automatically delete the oldest version.
                      Do you want to continue?
                    </>
                  );
                }
                return (
                  <>
                    You have <strong>{history?.length}</strong> versions but
                    the limit is <strong>{maxEntries}</strong>. Saving a new
                    version will automatically delete the{" "}
                    <strong>{pruneCount}</strong> oldest versions. Do you want
                    to continue?
                  </>
                );
              })()}
            </p>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPruneWarning(false)}
              >
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={doCreateSnapshot}
                loading={isCreating}
              >
                Continue
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
