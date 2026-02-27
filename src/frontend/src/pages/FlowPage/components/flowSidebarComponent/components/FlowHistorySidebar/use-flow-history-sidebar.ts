import { useQueryClient } from "@tanstack/react-query";
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
  usePostCreateSnapshot,
} from "@/controllers/API/queries/flow-history";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useVersionPreviewStore from "@/stores/historyPreviewStore";
import type { FlowVersionEntry } from "@/types/flow/history";
import {
  downloadFlow,
  processFlows,
  removeApiKeys,
} from "@/utils/reactflowUtils";
import { CURRENT_DRAFT_ID } from "./constants";

export function useFlowVersionSidebar(flowId: string) {
  const queryClient = useQueryClient();
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

  const applyFlowToCanvas = useApplyFlowToCanvas();
  const currentFlow = useFlowStore((s) => s.currentFlow);

  const { mutate: deleteEntry, isPending: isDeleting } =
    useDeleteVersionEntry();

  const [pruneWarning, setPruneWarning] = useState(false);
  const [animatingId, setAnimatingId] = useState<string | null>(null);
  const prevVersionsLengthRef = useRef<number>(0);

  const [restoreDialogEntry, setRestoreDialogEntry] =
    useState<FlowVersionEntry | null>(null);
  const [deleteDialogEntry, setDeleteDialogEntry] =
    useState<FlowVersionEntry | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);

  const {
    data: versionsResponse,
    isLoading,
    isError: isListError,
  } = useGetFlowVersions({ flowId }, { refetchInterval: 10000 });

  const versions = versionsResponse?.entries;
  const maxEntries = versionsResponse?.max_entries;

  useEffect(() => {
    const newLen = versions?.length ?? 0;
    if (newLen > prevVersionsLengthRef.current && versions?.[0]) {
      setAnimatingId(versions[0].id);
      const t = setTimeout(() => setAnimatingId(null), 500);
      prevVersionsLengthRef.current = newLen;
      return () => clearTimeout(t);
    }
    prevVersionsLengthRef.current = newLen;
  }, [versions]);

  const { mutate: createSnapshot, isPending: isCreating } =
    usePostCreateSnapshot();

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
  } | null>(() => {
    if (selectedId === CURRENT_DRAFT_ID || !selectedEntryFull?.data)
      return null;

    try {
      const clonedData = cloneDeep(selectedEntryFull.data);
      const flow = { data: clonedData, is_component: false } as any;
      processFlows([flow]);
      return { nodes: flow.data.nodes, edges: flow.data.edges };
    } catch (err) {
      console.error("Failed to process version flow data for preview:", err);
      return { nodes: [], edges: [], error: true };
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
        nodes: cloneDeep(useFlowStore.getState().nodes),
        edges: cloneDeep(useFlowStore.getState().edges),
      });
    }
  }, [processedPreview, selectedId]);

  useEffect(() => {
    if (processedPreview?.error) {
      setErrorData({
        title: "This version's data could not be rendered for preview",
      });
    }
  }, [processedPreview?.error, setErrorData]);

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
        cloneDeep(useFlowStore.getState().nodes),
        cloneDeep(useFlowStore.getState().edges),
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
      useFlowStore.setState({
        nodes: cloneDeep(useFlowStore.getState().nodes),
        edges: cloneDeep(useFlowStore.getState().edges),
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

  const handleSelectEntry = useCallback((entryId: string) => {
    setSelectedId(entryId);
  }, []);

  const doCreateSnapshot = useCallback(() => {
    createSnapshot(
      { flowId, description: null },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ["useGetFlowVersions"] });
          setSuccessData({ title: "Version saved" });
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
  }, [flowId, createSnapshot, queryClient, setSuccessData, setErrorData]);

  const handleCreateSnapshot = useCallback(() => {
    if (versions && maxEntries && versions.length >= maxEntries) {
      setPruneWarning(true);
      return;
    }
    doCreateSnapshot();
  }, [versions, maxEntries, doCreateSnapshot]);

  const handleRestore = useCallback(
    async (entry: FlowVersionEntry) => {
      setRestoreDialogEntry(null);
      setIsRestoring(true);
      try {
        const response = await api.post(
          `${getURL("FLOWS")}/${flowId}/versions/${entry.id}/activate`,
          null,
          { params: { save_draft: true } },
        );
        const updatedFlow = response.data;
        queryClient.invalidateQueries({ queryKey: ["useGetFlowVersions"] });
        const flow = {
          ...updatedFlow,
          data: {
            nodes: updatedFlow.data?.nodes ?? [],
            edges: updatedFlow.data?.edges ?? [],
          },
        };
        applyFlowToCanvas(flow);
        clearPreview();
        setSuccessData({ title: "Version restored" });
      } catch (err: any) {
        const detail = err?.response?.data?.detail;
        setErrorData({
          title: "Failed to restore version",
          ...(detail ? { list: [detail] } : {}),
        });
      } finally {
        setIsRestoring(false);
      }
    },
    [
      flowId,
      queryClient,
      applyFlowToCanvas,
      clearPreview,
      setSuccessData,
      setErrorData,
    ],
  );

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
        downloadFlow(flowToExport, flowName);
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
            queryClient.invalidateQueries({ queryKey: ["useGetFlowVersions"] });
            setSuccessData({ title: "Version deleted" });
            if (nextEntry) {
              setPreview([], [], nextEntry.version_tag, nextEntry.id);
            } else {
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
    [
      flowId,
      versions,
      deleteEntry,
      queryClient,
      setSuccessData,
      setErrorData,
      setPreview,
      clearPreview,
    ],
  );

  const isViewingDraft = selectedId === CURRENT_DRAFT_ID;

  return {
    selectedId,
    pruneWarning,
    setPruneWarning,
    animatingId,
    restoreDialogEntry,
    setRestoreDialogEntry,
    deleteDialogEntry,
    setDeleteDialogEntry,
    isRestoring,
    versions,
    maxEntries,
    isLoading,
    isListError,
    isEntryError,
    processedPreview,
    isCreating,
    isDeleting,
    isViewingDraft,
    handleSelectEntry,
    doCreateSnapshot,
    handleCreateSnapshot,
    handleRestore,
    handleExport,
    handleDelete,
  };
}
