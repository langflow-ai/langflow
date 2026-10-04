import { cloneDeep } from "lodash";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import {
  useGetFlowHistoryTimeline,
  useGetFlowRevision,
  useGetFlowRevisions,
} from "@/controllers/API/queries/flow-revisions";
import {
  useDeleteVersionEntry,
  useGetFlowVersionEntry,
  useGetFlowVersions,
} from "@/controllers/API/queries/flow-version";
import { useFlowNames } from "@/hooks/use-history-changes";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useRevisionPlaybackStore from "@/stores/revisionPlaybackStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";
import type { FlowVersionEntry } from "@/types/flow/version";
import {
  type DescribeOptions,
  describeOperation,
  fieldLabelsFrom,
} from "@/utils/flow-operations/describe";
import {
  entryContaining,
  graphAt,
  operationAt,
} from "@/utils/flow-operations/history";
import {
  cleanEdges,
  downloadFlow,
  processFlows,
  removeApiKeys,
} from "@/utils/reactflowUtils";
import {
  CURRENT_DRAFT_ID,
  revisionOfSelection,
  revisionSelectionId,
} from "./constants";
import { summarizeEntry } from "./fold";
import { formatTimestamp } from "./utils";

export function useFlowVersionSidebar(flowId: string) {
  const { t } = useTranslation();
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
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  const originalDraftNodesRef = useRef<any[] | null>(null);
  // biome-ignore lint/suspicious/noExplicitAny: legacy
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

  const {
    data: revisionPages,
    fetchNextPage: loadOlderEntries,
    hasNextPage: hasOlderEntries,
    isFetchingNextPage: isLoadingOlderEntries,
  } = useGetFlowRevisions(flowId, { refetchInterval: 10000 });
  const timelineEntries = useMemo(
    () => revisionPages?.pages.flatMap((page) => page.entries) ?? [],
    [revisionPages],
  );
  const earliestRevision = revisionPages?.pages[0]?.earliest_revision ?? null;
  const latestRevision = revisionPages?.pages[0]?.latest_revision ?? null;
  // Every retained revision, replayed, so the history slider and any
  // selection can be drawn without asking the server again.
  const { data: historyTimeline } = useGetFlowHistoryTimeline(
    flowId,
    latestRevision,
  );
  const setPlaybackTimeline = useRevisionPlaybackStore((s) => s.setTimeline);
  const setPlaybackRevision = useRevisionPlaybackStore((s) => s.setRevision);
  const setSelectRevision = useRevisionPlaybackStore(
    (s) => s.setSelectRevision,
  );
  useEffect(() => {
    setPlaybackTimeline(historyTimeline ?? null);
  }, [historyTimeline, setPlaybackTimeline]);
  useEffect(() => {
    setSelectRevision((revision) =>
      setSelectedId(revisionSelectionId(revision)),
    );
    return () => {
      setSelectRevision(null);
      setPlaybackTimeline(null);
      setPlaybackRevision(null);
    };
  }, [setSelectRevision, setPlaybackTimeline, setPlaybackRevision]);
  // Field labels and names for the timeline text, from the flow as it is
  // now, then from its history.
  const names = useFlowNames(timelineEntries);
  const describeOptions = useMemo<DescribeOptions>(
    () => ({ fieldLabel: fieldLabelsFrom(currentFlow?.data), names }),
    [currentFlow?.data, names],
  );
  // Saved versions the timeline cannot place: saved before the flow had
  // history, or older than the history still retained.
  const olderVersions = useMemo(
    () =>
      (versions ?? []).filter(
        (version) =>
          version.operation_revision == null ||
          earliestRevision === null ||
          version.operation_revision < earliestRevision,
      ),
    [versions, earliestRevision],
  );

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

  const selectedRevision = revisionOfSelection(selectedId);
  // Before paint, like the canvas swap below: what the previewed point
  // changed is drawn from this, so it must never outlast the preview onto
  // the live canvas, even for a frame.
  useLayoutEffect(() => {
    setPlaybackRevision(selectedRevision);
  }, [selectedRevision, setPlaybackRevision]);
  // The slider can stop inside an entry; the entry stays selected throughout.
  const selectedTimelineEntry =
    selectedRevision === null
      ? undefined
      : entryContaining(timelineEntries, selectedRevision);
  const localGraph =
    historyTimeline && selectedRevision !== null
      ? graphAt(historyTimeline, selectedRevision)
      : null;
  const operationHere =
    historyTimeline && selectedRevision !== null
      ? operationAt(historyTimeline, selectedRevision)
      : null;
  const selectedVersionId =
    selectedId !== CURRENT_DRAFT_ID && selectedRevision === null
      ? selectedId
      : "";
  const {
    data: selectedVersionFull,
    isLoading: isLoadingVersion,
    isError: isVersionError,
  } = useGetFlowVersionEntry(
    { flowId, versionId: selectedVersionId },
    { enabled: !!selectedVersionId, gcTime: 0, staleTime: 0 },
  );
  const {
    data: selectedRevisionGraph,
    isLoading: isLoadingRevision,
    isError: isRevisionError,
  } = useGetFlowRevision(
    // Asked of the server only until the replayed history is ready.
    { flowId, revision: localGraph ? null : selectedRevision },
    { gcTime: 0, staleTime: 0 },
  );
  const isLoadingEntry =
    (!!selectedVersionId && isLoadingVersion) ||
    (selectedRevision !== null && isLoadingRevision);
  const isEntryError = isVersionError || isRevisionError;
  // A timeline entry previews like a version: the flow at its last revision,
  // labelled by when it was recorded and summarized by what changed.
  const revisionData = localGraph ?? selectedRevisionGraph?.data;
  const atEntryEnd = selectedTimelineEntry?.end_revision === selectedRevision;
  const selectedEntryFull =
    selectedRevision !== null
      ? revisionData && {
          data: revisionData,
          version_tag: selectedTimelineEntry?.created_at
            ? formatTimestamp(selectedTimelineEntry.created_at)
            : t("flowHistory.previewLabel"),
          // At an entry's end, everything the entry changed; inside it, the
          // one change that produced this point.
          description:
            !atEntryEnd && operationHere
              ? `${operationHere.actor.username ?? t("flowHistory.unknownAuthor")}: ${describeOperation(operationHere, t, describeOptions).join("; ")}`
              : selectedTimelineEntry
                ? summarizeEntry(selectedTimelineEntry, t, describeOptions)
                : null,
        }
      : selectedVersionFull;

  useEffect(() => {
    setPreviewLoading(isLoadingEntry);
  }, [isLoadingEntry, setPreviewLoading]);

  const processedPreview = useMemo<{
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    nodes: any[];
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    edges: any[];
    error?: boolean;
    errorMessage?: string;
  } | null>(() => {
    if (selectedId === CURRENT_DRAFT_ID || !selectedEntryFull?.data)
      return null;

    try {
      const clonedData = cloneDeep(selectedEntryFull.data);
      // biome-ignore lint/suspicious/noExplicitAny: legacy
      const flow = { data: clonedData, is_component: false } as any;
      processFlows([flow]);
      // As when a flow is opened: rebuild the edges' handle ids from the
      // nodes, or edges stored in another spelling attach to nothing.
      const { edges } = cleanEdges(flow.data.nodes, flow.data.edges);
      return { nodes: flow.data.nodes, edges };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      console.error("Failed to process version flow data for preview:", err);
      return { nodes: [], edges: [], error: true, errorMessage };
    }
  }, [selectedId, selectedEntryFull?.data]);

  // Whether the canvas was ever swapped away from the draft. Restoring is only
  // meaningful after that: writing the draft back over itself replaces every
  // node with a clone of equal content but new identity, and the autosave that
  // follows records the person as having edited a flow they only looked at —
  // which is enough to turn the next version check into a conflict dialog about
  // changes they never made.
  const previewedSomething = useRef(false);

  useLayoutEffect(() => {
    if (processedPreview && !processedPreview.error) {
      previewedSomething.current = true;
      useFlowStore.setState({
        nodes: processedPreview.nodes,
        edges: processedPreview.edges,
      });
    } else if (
      previewedSomething.current &&
      (selectedId === CURRENT_DRAFT_ID || processedPreview?.error)
    ) {
      useFlowStore.setState({
        nodes: cloneDeep(originalDraftNodesRef.current),
        edges: cloneDeep(originalDraftEdgesRef.current),
      });
    }
    // The viewport is left alone: moving through history keeps the same part
    // of the canvas in view, so changes can be compared in place.
  }, [processedPreview, selectedId]);

  useEffect(() => {
    if (processedPreview?.error) {
      setErrorData({
        title: t("flowVersion.dataCannotBeRendered"),
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
        selectedEntryFull?.description ?? null,
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
    selectedEntryFull?.description,
    setPreview,
  ]);

  // biome-ignore lint/suspicious/noExplicitAny: legacy
  const autoSaveFnRef = useRef<any>(null);
  const inspectionPanelWasVisible = useRef(false);
  useLayoutEffect(() => {
    // biome-ignore lint/suspicious/noExplicitAny: legacy
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
        // Same reason as the effect above: with nothing previewed there is
        // nothing to put back, and putting it back anyway looks like an edit.
        if (!wasRestored && previewedSomething.current) {
          useFlowStore.setState({
            nodes: cloneDeep(originalDraftNodesRef.current),
            edges: cloneDeep(originalDraftEdgesRef.current),
          });
        }
      } catch (err) {
        console.error("Version sidebar cleanup: failed to restore draft", err);
      }

      try {
        useRevisionPlaybackStore.getState().setRevision(null);
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
          setErrorData({ title: t("errors.noDataToExport") });
          return;
        }
        const flowName = `${currentFlow?.name || "flow"}_${tag}`;
        const flowToExport = removeApiKeys({
          id: currentFlow?.id ?? "",
          data,
          name: flowName,
          description: currentFlow?.description ?? "",
          is_component: false,
          // biome-ignore lint/suspicious/noExplicitAny: legacy
        } as any);
        downloadFlow(flowToExport, flowName, currentFlow?.description ?? "");
        // biome-ignore lint/suspicious/noExplicitAny: legacy
      } catch (err: any) {
        const detail = err?.response?.data?.detail;
        const message = detail ?? err?.message ?? "Unknown error";
        setErrorData({
          title: t("errors.failedToExportVersion"),
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
            setSuccessData({ title: t("success.versionDeleted") });
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
          // biome-ignore lint/suspicious/noExplicitAny: legacy
          onError: (err: any) => {
            const detail = err?.response?.data?.detail;
            setErrorData({
              title: t("errors.failedToDeleteVersion"),
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
    timelineEntries,
    selectedTimelineEntryId: selectedTimelineEntry?.id ?? null,
    describeOptions,
    olderVersions,
    hasOlderEntries,
    isLoadingOlderEntries,
    loadOlderEntries,
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
