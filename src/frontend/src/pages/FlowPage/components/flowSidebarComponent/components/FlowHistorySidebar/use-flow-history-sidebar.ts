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
import { useSearchParams } from "react-router-dom";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import {
  useDeleteFlowVersionEntry,
  useGetFlowVersionEntry,
  useGetFlowVersions,
  usePostCreateVersionSnapshot,
} from "@/controllers/API/queries/flow-version";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useHistoryPreviewStore from "@/stores/historyPreviewStore";
import type { FlowType } from "@/types/flow";
import type { FlowVersionEntry } from "@/types/flow/version";
import {
  downloadFlow,
  processFlows,
  removeApiKeys,
} from "@/utils/reactflowUtils";
import { CURRENT_DRAFT_ID } from "./constants";

type PreviewGraphData = {
  nodes: NonNullable<FlowType["data"]>["nodes"];
  edges: NonNullable<FlowType["data"]>["edges"];
  error?: boolean;
};

type AutoSaveFlowFn = ((flow?: FlowType) => void) & {
  flush?: () => void;
};

function getErrorDetail(error: unknown): string | undefined {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as { response?: { data?: { detail?: string } } })
      .response;
    return response?.data?.detail;
  }
  return undefined;
}

export function useFlowHistorySidebar(flowId: string) {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setPreview = useHistoryPreviewStore((s) => s.setPreview);
  const clearPreview = useHistoryPreviewStore((s) => s.clearPreview);
  const setPreviewLoading = useHistoryPreviewStore((s) => s.setPreviewLoading);
  const storePreviewId = useHistoryPreviewStore((s) => s.previewId);

  const [selectedId, setSelectedId] = useState<string>(CURRENT_DRAFT_ID);
  const requestedVersionId =
    searchParams.get("versionId") ?? searchParams.get("historyId");

  useEffect(() => {
    setSelectedId(storePreviewId ?? CURRENT_DRAFT_ID);
  }, [storePreviewId]);

  const applyFlowToCanvas = useApplyFlowToCanvas();
  const currentFlow = useFlowStore((s) => s.currentFlow);

  const { mutate: deleteEntry, isPending: isDeleting } =
    useDeleteFlowVersionEntry();

  const [pruneWarning, setPruneWarning] = useState(false);
  const [animatingId, setAnimatingId] = useState<string | null>(null);
  const prevHistoryLengthRef = useRef<number>(0);

  const [restoreDialogEntry, setRestoreDialogEntry] =
    useState<FlowVersionEntry | null>(null);
  const [deleteDialogEntry, setDeleteDialogEntry] =
    useState<FlowVersionEntry | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);

  const {
    data: historyResponse,
    isLoading,
    isError: isListError,
  } = useGetFlowVersions({ flowId }, { refetchInterval: 10000 });

  const history = historyResponse?.entries;
  const maxEntries = historyResponse?.max_entries;
  useEffect(() => {
    if (!requestedVersionId || !history?.length) {
      return;
    }
    const hasRequestedEntry = history.some(
      (entry) => entry.id === requestedVersionId,
    );
    if (hasRequestedEntry) {
      setSelectedId(requestedVersionId);
    }
  }, [history, requestedVersionId]);

  const deploymentCountsByHistoryId = historyResponse?.deployment_counts ?? {};

  useEffect(() => {
    const newLen = history?.length ?? 0;
    if (newLen > prevHistoryLengthRef.current && history?.[0]) {
      setAnimatingId(history[0].id);
      const t = setTimeout(() => setAnimatingId(null), 500);
      prevHistoryLengthRef.current = newLen;
      return () => clearTimeout(t);
    }
    prevHistoryLengthRef.current = newLen;
  }, [history]);

  const { mutate: createSnapshot, isPending: isCreating } =
    usePostCreateVersionSnapshot();

  const selectedHistoryId = selectedId !== CURRENT_DRAFT_ID ? selectedId : "";
  const {
    data: selectedEntryFull,
    isLoading: isLoadingEntry,
    isError: isEntryError,
  } = useGetFlowVersionEntry(
    { flowId, versionId: selectedHistoryId },
    { enabled: !!selectedHistoryId, gcTime: 0, staleTime: 0 },
  );

  useEffect(() => {
    setPreviewLoading(isLoadingEntry);
  }, [isLoadingEntry, setPreviewLoading]);

  const processedPreview = useMemo<PreviewGraphData | null>(() => {
    if (selectedId === CURRENT_DRAFT_ID || !selectedEntryFull?.data)
      return null;

    try {
      const clonedData = cloneDeep(selectedEntryFull.data);
      const flow: FlowType = {
        id: currentFlow?.id ?? "",
        name: currentFlow?.name ?? "flow",
        description: currentFlow?.description ?? "",
        data: clonedData as FlowType["data"],
        is_component: false,
      };
      processFlows([flow]);
      if (!flow.data) {
        return { nodes: [], edges: [], error: true };
      }
      return { nodes: flow.data.nodes, edges: flow.data.edges };
    } catch (err) {
      console.error("Failed to process historical flow data for preview:", err);
      return { nodes: [], edges: [], error: true };
    }
  }, [selectedId, selectedEntryFull?.data, currentFlow]);

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

  const autoSaveFnRef = useRef<AutoSaveFlowFn | null>(null);
  const inspectionPanelWasVisible = useRef(false);
  useLayoutEffect(() => {
    const currentAutoSave = useFlowStore.getState().autoSaveFlow as
      | AutoSaveFlowFn
      | undefined;
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
        onError: (err: unknown) => {
          const detail = getErrorDetail(err);
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
    if (history && maxEntries && history.length >= maxEntries) {
      setPruneWarning(true);
      return;
    }
    doCreateSnapshot();
  }, [history, maxEntries, doCreateSnapshot]);

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
        processFlows([flow]);
        applyFlowToCanvas(flow);
        clearPreview();
        setSuccessData({ title: "Version restored" });
      } catch (err: unknown) {
        const detail = getErrorDetail(err);
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
          data: data as FlowType["data"],
          name: flowName,
          description: currentFlow?.description ?? "",
          is_component: false,
        } as FlowType);
        downloadFlow(flowToExport, flowName);
      } catch (err: unknown) {
        const detail = getErrorDetail(err);
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
      const entries = history ?? [];
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
          onError: (err: unknown) => {
            const detail = getErrorDetail(err);
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
      history,
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
    history,
    maxEntries,
    isLoading,
    isListError,
    isEntryError,
    processedPreview,
    isCreating,
    isDeleting,
    isViewingDraft,
    deploymentCountsByHistoryId,
    handleSelectEntry,
    doCreateSnapshot,
    handleCreateSnapshot,
    handleRestore,
    handleExport,
    handleDelete,
  };
}
