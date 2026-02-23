import { useQueryClient } from "@tanstack/react-query";
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
import useHistoryPreviewStore from "@/stores/historyPreviewStore";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import {
  downloadFlow,
  processFlows,
  removeApiKeys,
} from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import { cloneDeep } from "lodash";

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
// Constants
// ---------------------------------------------------------------------------

const CURRENT_DRAFT_ID = "__current_draft__";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface FlowHistorySidebarContentProps {
  flowId: string;
}

export default function FlowHistorySidebarContent({
  flowId,
}: FlowHistorySidebarContentProps) {
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const applyFlowToCanvas = useApplyFlowToCanvas();
  const setPreview = useHistoryPreviewStore((s) => s.setPreview);
  const clearPreview = useHistoryPreviewStore((s) => s.clearPreview);

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

  // Capture the original store state when the sidebar mounts so we can
  // restore it when the sidebar closes or the user switches to Current Draft.
  const originalStoreRef = useRef({
    nodes: cloneDeep(useFlowStore.getState().nodes),
    edges: cloneDeep(useFlowStore.getState().edges),
  });

  // Flag to temporarily disable the guard subscription during doRestore.
  // Without this, applyFlowToCanvas triggers a store change that the guard
  // detects and overwrites with the old preview data.
  const guardDisabledRef = useRef(false);

  // Flush any pending debounced auto-save, then disable it while the history
  // sidebar is open. The canvas is read-only in history mode (preview overlay
  // always visible), so no new changes need saving.
  //
  // We flush (not cancel) on mount so that any recent edits are saved to the
  // server before we snapshot. This is safe because the store still contains
  // the real draft data at this point — preview data is set up by later effects.
  const autoSaveFnRef = useRef<any>(null);
  const inspectionPanelWasVisible = useRef(false);
  useLayoutEffect(() => {
    const currentAutoSave = useFlowStore.getState().autoSaveFlow as any;
    if (currentAutoSave) {
      // Flush pending debounce so latest edits are persisted to the server
      if (typeof currentAutoSave.flush === "function") {
        currentAutoSave.flush();
      }
      autoSaveFnRef.current = currentAutoSave;
      useFlowStore.setState({ autoSaveFlow: undefined });
    }

    inspectionPanelWasVisible.current =
      useFlowStore.getState().inspectionPanelVisible;
    if (inspectionPanelWasVisible.current) {
      useFlowStore.setState({ inspectionPanelVisible: false });
    }

    return () => {
      // Restore store state BEFORE re-enabling auto-save so that an
      // immediate auto-save trigger doesn't persist preview data.
      useFlowStore.setState({
        nodes: originalStoreRef.current.nodes,
        edges: originalStoreRef.current.edges,
      });
      clearPreview();

      if (autoSaveFnRef.current) {
        useFlowStore.setState({ autoSaveFlow: autoSaveFnRef.current });
        autoSaveFnRef.current = null;
      }
      if (inspectionPanelWasVisible.current) {
        useFlowStore.setState({ inspectionPanelVisible: true });
        inspectionPanelWasVisible.current = false;
      }
    };
  }, [clearPreview]);

  // Process historical data through the same pipeline used by
  // useApplyFlowToCanvas for normal flow loading: processFlows().
  // This avoids duplicating the 4-step processing pipeline.
  const processedPreview = useMemo<{
    nodes: any[];
    edges: any[];
    error?: boolean;
  } | null>(() => {
    if (selectedId === CURRENT_DRAFT_ID || !selectedEntryFull?.data)
      return null;

    try {
      const clonedData = cloneDeep(selectedEntryFull.data);
      const flow = { data: clonedData, is_component: false } as any;
      processFlows([flow]);
      return { nodes: flow.data.nodes, edges: flow.data.edges };
    } catch (err) {
      console.error(
        "Failed to process historical flow data for preview:",
        err,
      );
      return { nodes: [], edges: [], error: true };
    }
  }, [selectedId, selectedEntryFull?.data]);

  // Sync the global flow store with whatever version is being previewed.
  // GenericNode and its sub-components read edges/nodes from the store, so
  // this ensures handle visibility and connection state match the preview.
  //
  // Uses useLayoutEffect (not useEffect) to match the old FlowHistoryPanel —
  // synchronous before paint prevents a flash of stale data.
  //
  // Important: when processedPreview is null but selectedId is NOT
  // CURRENT_DRAFT_ID, the new entry is still loading. In that case we keep
  // whatever is currently on the canvas (either the previous version's
  // preview or the draft) instead of flashing back to the draft.
  useLayoutEffect(() => {
    if (processedPreview && !processedPreview.error) {
      useFlowStore.setState({
        nodes: processedPreview.nodes,
        edges: processedPreview.edges,
      });
    } else if (selectedId === CURRENT_DRAFT_ID || processedPreview?.error) {
      useFlowStore.setState({
        nodes: originalStoreRef.current.nodes,
        edges: originalStoreRef.current.edges,
      });
    }
    // When selectedId is a history entry but processedPreview is null,
    // the entry is loading — keep the canvas as-is.
  }, [processedPreview, selectedId]);

  // Push preview state to the preview store so PageComponent shows the
  // read-only overlay. The overlay is ALWAYS shown while the history panel
  // is open — even for Current Draft — making the canvas fully read-only.
  useEffect(() => {
    if (
      processedPreview &&
      !processedPreview.error &&
      selectedId !== CURRENT_DRAFT_ID
    ) {
      const tag = selectedEntryFull?.version_tag ?? "";
      setPreview(processedPreview.nodes, processedPreview.edges, tag);
    } else if (selectedId === CURRENT_DRAFT_ID || processedPreview?.error) {
      // Show draft data in the read-only overlay
      setPreview(
        originalStoreRef.current.nodes,
        originalStoreRef.current.edges,
        "Current Draft",
      );
    }
    // When loading a new entry, keep the previous preview overlay visible.
  }, [processedPreview, selectedId, selectedEntryFull?.version_tag, setPreview]);

  // Guard: if something external (e.g. an in-flight save completing)
  // overwrites the store while we're previewing, re-apply immediately.
  //
  // MUST be useLayoutEffect so that cleanup (unsubscribe) runs synchronously
  // before the store-sync useLayoutEffect sets new state. If this were
  // useEffect, the old subscription would still be active when the store-sync
  // restores the draft, and it would immediately overwrite the draft with the
  // old preview data.
  useLayoutEffect(() => {
    // Reset the guard-disabled flag at every effect boundary. doRestore
    // sets it to true and relies on the next render cycle (which triggers
    // this effect) to reset it, avoiding a race with async store writes
    // from refreshAllModelInputs.
    guardDisabledRef.current = false;

    if (!processedPreview || processedPreview.error) return;

    const unsub = useFlowStore.subscribe((state) => {
      if (!guardDisabledRef.current && state.nodes !== processedPreview.nodes) {
        useFlowStore.setState({
          nodes: processedPreview.nodes,
          edges: processedPreview.edges,
        });
      }
    });

    return unsub;
  }, [processedPreview]);

  // Escape key dismisses dialogs
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (pruneWarning) {
          setPruneWarning(false);
        } else if (deleteTarget) {
          setDeleteTarget(null);
        } else if (restoreConfirm) {
          setRestoreConfirm(null);
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [restoreConfirm, deleteTarget, pruneWarning]);

  const handleSelectEntry = useCallback((entryId: string) => {
    setSelectedId(entryId);
  }, []);

  const doCreateSnapshot = useCallback(() => {
    createSnapshot(
      { flowId, description: description || null },
      {
        onSuccess: () => {
          // Immediately refresh the version list
          queryClient.invalidateQueries({
            queryKey: ["useGetFlowHistory"],
          });
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
  }, [flowId, description, createSnapshot, queryClient, setSuccessData, setErrorData]);

  const handleCreateSnapshot = useCallback(() => {
    if (history && maxEntries && history.length >= maxEntries) {
      setPruneWarning(true);
      return;
    }
    doCreateSnapshot();
  }, [history, maxEntries, doCreateSnapshot]);

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
        const detail = err?.response?.data?.detail;
        setErrorData({
          title: "Failed to restore version",
          ...(detail ? { list: [detail] } : {}),
        });
        setIsRestoring(false);
        setRestoreConfirm(null);
        return;
      }

      // Kick off the history list refetch immediately so it runs in parallel
      // with the canvas work below (applyFlowToCanvas is synchronous but heavy).
      queryClient.invalidateQueries({
        queryKey: ["useGetFlowHistory"],
      });

      try {
        // Disable the guard so applyFlowToCanvas can write to the store
        // without the subscription overwriting it with old preview data.
        guardDisabledRef.current = true;

        applyFlowToCanvas(updatedFlow);

        // Update the ref so unmount cleanup restores the new (restored) data.
        originalStoreRef.current = {
          nodes: useFlowStore.getState().nodes,
          edges: useFlowStore.getState().edges,
        };

        // Immediately show the new draft in the read-only overlay
        setPreview(
          originalStoreRef.current.nodes,
          originalStoreRef.current.edges,
          "Current Draft",
        );

        // Do NOT re-enable the guard here. Async operations from
        // applyFlowToCanvas (e.g. refreshAllModelInputs) may fire after
        // this and the old guard subscription would overwrite the restored
        // data with stale preview. The guard useLayoutEffect will reset
        // guardDisabledRef when it next runs (on re-render).

        setSuccessData({ title: "Version restored" });
        setSelectedId(CURRENT_DRAFT_ID);

        requestAnimationFrame(() => {
          useFlowStore.getState().reactFlowInstance?.fitView({
            padding: 0.2,
            minZoom: 0.25,
            maxZoom: 2,
          });
        });
      } catch {
        setErrorData({
          title:
            "Version restored on server, but there was an issue rendering it. Please refresh the page.",
        });
      } finally {
        setIsRestoring(false);
        setRestoreConfirm(null);
      }
    },
    [
      flowId,
      saveDraftOnRestore,
      applyFlowToCanvas,
      setPreview,
      queryClient,
      setSuccessData,
      setErrorData,
    ],
  );

  const handleDelete = useCallback(
    (historyId: string) => {
      deleteEntry(
        { flowId, historyId },
        {
          onSuccess: () => {
            queryClient.invalidateQueries({
              queryKey: ["useGetFlowHistory"],
            });
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
    [flowId, selectedId, deleteEntry, queryClient, setSuccessData, setErrorData],
  );

  const handleExportEntry = useCallback(
    async (entryId: string) => {
      try {
        let data: any;
        let tag: string;

        if (entryId === CURRENT_DRAFT_ID) {
          // Use originalStoreRef instead of currentFlow?.data because during
          // preview the store may contain preview data, and currentFlow.data
          // may not reflect the actual draft nodes/edges.
          data = {
            ...currentFlow?.data,
            nodes: originalStoreRef.current.nodes,
            edges: originalStoreRef.current.edges,
          };
          tag = "draft";
        } else {
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

  const isViewingDraft = selectedId === CURRENT_DRAFT_ID;

  return (
    <>
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-3 py-3">
          <span className="text-sm font-semibold">Version History</span>
        </div>

        {/* Error loading entry */}
        {isEntryError && (
          <div className="flex items-center gap-2 border-b bg-destructive/10 px-3 py-2">
            <span className="text-xs text-destructive">
              Failed to load version data
            </span>
          </div>
        )}

        {/* Error processing entry data */}
        {processedPreview?.error && (
          <div className="flex items-center gap-2 border-b bg-destructive/10 px-3 py-2">
            <span className="text-xs text-destructive">
              This version's data could not be rendered for preview
            </span>
          </div>
        )}

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
          {/* Current Draft row */}
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
              {history.length}
              {maxEntries ? ` / ${maxEntries}` : ""} versions
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
          {!isLoading &&
            !isListError &&
            (!history || history.length === 0) && (
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
                <div className="w-3 shrink-0" />
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
                  <DropdownMenuContent align="end" className="w-44">
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

      {/* Restore confirmation dialog — portaled to body */}
      {restoreConfirm &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
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
              <label className="flex cursor-pointer items-center gap-2">
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
          </div>,
          document.body,
        )}

      {/* Delete confirmation dialog — portaled to body */}
      {deleteTarget &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
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
          </div>,
          document.body,
        )}

      {/* Loading entry overlay — portaled to body so it doesn't push the version list */}
      {isLoadingEntry &&
        createPortal(
          <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center">
            <div className="pointer-events-auto flex items-center gap-2 rounded-lg border bg-background px-4 py-2 shadow-lg">
              <ForwardedIconComponent
                name="Loader2"
                className="h-4 w-4 animate-spin text-muted-foreground"
              />
              <span className="text-sm text-muted-foreground">
                Loading preview...
              </span>
            </div>
          </div>,
          document.body,
        )}

      {/* Prune warning dialog — portaled to body */}
      {pruneWarning &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
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
                  const pruneCount =
                    (history?.length ?? 0) + 1 - (maxEntries ?? 0);
                  if (pruneCount <= 1) {
                    return (
                      <>
                        You've reached the maximum of{" "}
                        <strong>{maxEntries}</strong> saved versions. Saving a
                        new version will automatically delete the oldest
                        version. Do you want to continue?
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
          </div>,
          document.body,
        )}
    </>
  );
}
