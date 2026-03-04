import { cloneDeep } from "lodash";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import {
  useDeleteVersionEntry,
  useGetFlowVersions,
  useGetFlowVersionEntry,
} from "@/controllers/API/queries/flow-version";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";
import type { FlowVersionEntry } from "@/types/flow/version";
import {
  downloadFlow,
  processFlows,
  removeApiKeys,
} from "@/utils/reactflowUtils";
import { CURRENT_DRAFT_ID } from "./constants";

export function useFlowVersionSidebar(flowId: string) {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setPreview = useVersionPreviewStore((s) => s.setPreview);
  const clearPreview = useVersionPreviewStore((s) => s.clearPreview);
  const setPreviewLoading = useVersionPreviewStore((s) => s.setPreviewLoading);
  const storePreviewId = useVersionPreviewStore((s) => s.previewId);

  const [selectedId, setSelectedId] = useState<string>(CURRENT_DRAFT_ID);

  useEffect(() => {
    setSelectedId(storePreviewId ?? CURRENT_DRAFT_ID);
  }, [storePreviewId]);

  const currentFlow = useFlowStore((s) => s.currentFlow);

  const { mutate: deleteEntry, isPending: isDeleting } =
    useDeleteVersionEntry();

  const [animatingId, setAnimatingId] = useState<string | null>(null);
  const prevVersionCountRef = useRef<number>(0);

  const [deleteDialogEntry, setDeleteDialogEntry] =
    useState<FlowVersionEntry | null>(null);

  // Capture original draft state on first render so we can restore it when
  // switching back to "Current" or on unmount. Initialized during render (not
  // in an effect) so the values are available before the preview layoutEffect.
  // Falls back to empty arrays if the store is not yet initialized to prevent
  // setting `undefined` into the store on cleanup.
  const originalDraftNodesRef = useRef<any[] | null>(null);
  const originalDraftEdgesRef = useRef<any[] | null>(null);
  if (originalDraftNodesRef.current === null) {
    originalDraftNodesRef.current =
      cloneDeep(useFlowStore.getState().nodes) ?? [];
    originalDraftEdgesRef.current =
      cloneDeep(useFlowStore.getState().edges) ?? [];
  }

  const {
    data: versionResponse,
    isLoading,
    isError: isListError,
  } = useGetFlowVersions({ flowId }, { refetchInterval: 10000 });

  const versions = versionResponse?.entries;
  const maxEntries = versionResponse?.max_entries;

  useEffect(() => {
    const newLen = versions?.length ?? 0;
    if (newLen > prevVersionCountRef.current && versions?.[0]) {
      setAnimatingId(versions[0].id);
      const t = setTimeout(() => setAnimatingId(null), 500);
      prevVersionCountRef.current = newLen;
      return () => clearTimeout(t);
    }
    prevVersionCountRef.current = newLen;
  }, [versions]);

  const selectedVersionId = selectedId !== CURRENT_DRAFT_ID ? selectedId : "";
  const {
    data: selectedEntryFull,
    isLoading: isLoadingEntry,
    isError: isEntryError,
  } = useGetFlowVersionEntry(
    { flowId, versionId: selectedVersionId },
    { enabled: !!selectedVersionId, gcTime: 0, staleTime: 0 },
  );

  useEffect(() => {
    setPreviewLoading(isLoadingEntry);
  }, [isLoadingEntry, setPreviewLoading]);

  const processedPreview = useMemo<{
    nodes: any[];
    edges: any[];
    error?: boolean;
    errorMessage?: string;
  } | null>(() => {
    if (selectedId === CURRENT_DRAFT_ID || !selectedEntryFull?.data)
      return null;

    try {
      const clonedData = cloneDeep(selectedEntryFull.data);
      const flow = { data: clonedData, is_component: false } as any;
      processFlows([flow]);
      return { nodes: flow.data.nodes, edges: flow.data.edges };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      console.error("Failed to process version flow data for preview:", err);
      return { nodes: [], edges: [], error: true, errorMessage };
    }
  }, [selectedId, selectedEntryFull?.data]);

  useLayoutEffect(() => {
    if (processedPreview && !processedPreview.error) {
      useFlowStore.setState({
        nodes: processedPreview.nodes,
        edges: processedPreview.edges,
      });
    } else if (selectedId === CURRENT_DRAFT_ID || processedPreview?.error) {
      useFlowStore.setState({
        nodes: cloneDeep(originalDraftNodesRef.current),
        edges: cloneDeep(originalDraftEdgesRef.current),
      });
    }
    // Fit the canvas to the new nodes after ReactFlow processes the state update.
    requestAnimationFrame(() => {
      useFlowStore.getState().reactFlowInstance?.fitView();
    });
  }, [processedPreview, selectedId]);

  useEffect(() => {
    if (processedPreview?.error) {
      setErrorData({
        title: "This version's data could not be rendered for preview",
        ...(processedPreview.errorMessage
          ? { list: [processedPreview.errorMessage] }
          : {}),
      });
    }
  }, [processedPreview?.error, processedPreview?.errorMessage, setErrorData]);

  useEffect(() => {
    if (
      processedPreview &&
      !processedPreview.error &&
      selectedId !== CURRENT_DRAFT_ID
    ) {
      const tag = selectedEntryFull?.version_tag ?? "";
      setPreview(
        processedPreview.nodes,
        processedPreview.edges,
        tag,
        selectedId,
      );
    } else if (selectedId === CURRENT_DRAFT_ID || processedPreview?.error) {
      setPreview(
        cloneDeep(originalDraftNodesRef.current),
        cloneDeep(originalDraftEdgesRef.current),
        "Current Draft",
        null,
      );
    }
  }, [
    processedPreview,
    selectedId,
    selectedEntryFull?.version_tag,
    setPreview,
  ]);

  const autoSaveFnRef = useRef<any>(null);
  const inspectionPanelWasVisible = useRef(false);
  useLayoutEffect(() => {
    const currentAutoSave = useFlowStore.getState().autoSaveFlow as any;
    if (currentAutoSave) {
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
      // Each cleanup step is isolated so a failure in one does not skip
      // the rest. Auto-save restoration is especially critical — if it is
      // skipped the user silently loses all future saves until page refresh.

      try {
        const wasRestored = useVersionPreviewStore.getState().didRestore;
        if (!wasRestored) {
          useFlowStore.setState({
            nodes: cloneDeep(originalDraftNodesRef.current),
            edges: cloneDeep(originalDraftEdgesRef.current),
          });
        }
      } catch (err) {
        console.error("Version sidebar cleanup: failed to restore draft", err);
      }

      try {
        clearPreview();
      } catch (err) {
        console.error("Version sidebar cleanup: failed to clear preview", err);
      }

      try {
        useVersionPreviewStore.setState({ didRestore: false });
      } catch (err) {
        console.error(
          "Version sidebar cleanup: failed to reset didRestore",
          err,
        );
      }

      try {
        if (autoSaveFnRef.current) {
          useFlowStore.setState({ autoSaveFlow: autoSaveFnRef.current });
          autoSaveFnRef.current = null;
        }
      } catch (err) {
        console.error(
          "Version sidebar cleanup: CRITICAL — failed to restore autoSaveFlow",
          err,
        );
      }

      try {
        if (inspectionPanelWasVisible.current) {
          useFlowStore.setState({ inspectionPanelVisible: true });
          inspectionPanelWasVisible.current = false;
        }
      } catch (err) {
        console.error(
          "Version sidebar cleanup: failed to restore inspection panel",
          err,
        );
      }
    };
  }, [clearPreview]);

  const handleSelectEntry = useCallback((entryId: string) => {
    setSelectedId(entryId);
  }, []);

  const handleExport = useCallback(
    async (entry: FlowVersionEntry) => {
      try {
        const response = await api.get(
          `${getURL("FLOWS")}/${flowId}/versions/${entry.id}`,
        );
        const data = response.data?.data;
        const tag = response.data?.version_tag ?? "version";
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
        downloadFlow(flowToExport, flowName, currentFlow?.description ?? "");
      } catch (err: any) {
        const detail = err?.response?.data?.detail;
        const message = detail ?? err?.message ?? "Unknown error";
        setErrorData({
          title: "Failed to export version",
          list: [message],
        });
      }
    },
    [flowId, currentFlow, setErrorData],
  );

  const handleDelete = useCallback(
    (entry: FlowVersionEntry) => {
      setDeleteDialogEntry(null);
      const entries = versions ?? [];
      const currentIndex = entries.findIndex((e) => e.id === entry.id);
      const nextEntry =
        currentIndex > 0
          ? entries[currentIndex - 1]
          : entries[currentIndex + 1];
      deleteEntry(
        { flowId, versionId: entry.id },
        {
          onSuccess: () => {
            setSuccessData({ title: "Version deleted" });
            // Select the next entry (triggers fetch + preview via existing
            // effects) instead of setting empty arrays into the store which
            // would cause a blank canvas flash.
            if (nextEntry) {
              setSelectedId(nextEntry.id);
            } else {
              setSelectedId(CURRENT_DRAFT_ID);
              clearPreview();
            }
          },
          onError: (err: any) => {
            const detail = err?.response?.data?.detail;
            setErrorData({
              title: "Failed to delete version",
              ...(detail ? { list: [detail] } : {}),
            });
          },
        },
      );
    },
    [flowId, versions, deleteEntry, setSuccessData, setErrorData, clearPreview],
  );

  const isViewingDraft = selectedId === CURRENT_DRAFT_ID;

  return {
    selectedId,
    animatingId,
    deleteDialogEntry,
    setDeleteDialogEntry,
    versions,
    maxEntries,
    isLoading,
    isListError,
    isEntryError,
    processedPreview,
    isDeleting,
    isViewingDraft,
    handleSelectEntry,
    handleExport,
    handleDelete,
  };
}
