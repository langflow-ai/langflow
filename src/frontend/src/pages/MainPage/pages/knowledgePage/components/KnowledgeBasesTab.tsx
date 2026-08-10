import type { CellKeyDownEvent, RowClickedEvent } from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import DataTableTab from "@/components/core/dataTableTabComponent";
import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type {
  IngestionRunInfo,
  PaginatedIngestionRunResponse,
} from "@/controllers/API/queries/knowledge-bases/use-get-ingestion-runs";
import {
  type KnowledgeBaseInfo,
  useGetKnowledgeBases,
} from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import KnowledgeBaseUploadModal from "@/modals/knowledgeBaseUploadModal/KnowledgeBaseUploadModal";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { updateIds } from "@/utils/reactflowUtils";
import { createKnowledgeBaseColumns } from "../config/knowledgeBaseColumns";
import { isBusyStatus } from "../config/statusConfig";
import { useKnowledgeBaseActions } from "../hooks/useKnowledgeBaseActions";
import { useKnowledgeBasePolling } from "../hooks/useKnowledgeBasePolling";
import { useOptimisticKnowledgeBase } from "../hooks/useOptimisticKnowledgeBase";
import type { KnowledgeBasesTabProps } from "../types";
import KnowledgeBaseEmptyState from "./KnowledgeBaseEmptyState";

interface IngestionFinishedToast {
  kind: "success" | "notice";
  title: string;
}

const formatIngestionFinishedTitle = (
  kbName: string,
  fallbackChunks: number,
  run: IngestionRunInfo | null,
): IngestionFinishedToast => {
  // Default fallback when the run lookup fails or returns nothing —
  // matches the legacy KB-cumulative-chunks message.
  if (!run) {
    return {
      kind: "success",
      title: `"${kbName}" ingestion complete — ${fallbackChunks} chunks ready`,
    };
  }

  const parts: string[] = [];
  if (run.succeeded > 0) {
    parts.push(`${run.succeeded} succeeded`);
  }
  if (run.skipped > 0) {
    parts.push(`${run.skipped} skipped`);
  }
  if (run.failed > 0) {
    parts.push(`${run.failed} failed`);
  }

  if (run.status === "succeeded") {
    return {
      kind: "success",
      title: `"${kbName}" ingestion complete — ${run.chunks_created} chunks ingested`,
    };
  }

  if (run.status === "partial") {
    const breakdown =
      parts.length > 0 ? parts.join(", ") : "no items processed";
    const chunkSuffix =
      run.chunks_created > 0 ? ` · ${run.chunks_created} chunks ingested` : "";
    return {
      kind: "notice",
      title: `"${kbName}" ingestion finished with issues — ${breakdown}${chunkSuffix}`,
    };
  }

  // Any other status (cancelled, failed reaching here unexpectedly, etc.)
  // falls back to a neutral notice using the run breakdown.
  const breakdown = parts.length > 0 ? parts.join(", ") : run.status;
  return {
    kind: "notice",
    title: `"${kbName}" ingestion ${run.status} — ${breakdown}`,
  };
};

const notifyOnIngestionFinished = async (
  kbDirName: string,
  kbDisplayName: string,
  fallbackChunks: number,
): Promise<IngestionFinishedToast> => {
  try {
    const res = await api.get<PaginatedIngestionRunResponse>(
      `${getURL("KNOWLEDGE_BASES")}/${kbDirName}/runs?page=1&limit=1`,
    );
    const latest = res.data?.runs?.[0] ?? null;
    return formatIngestionFinishedTitle(kbDisplayName, fallbackChunks, latest);
  } catch {
    return formatIngestionFinishedTitle(kbDisplayName, fallbackChunks, null);
  }
};

const KnowledgeBasesTab = ({
  quickFilterText,
  setQuickFilterText,
  selectedFiles,
  setSelectedFiles,
  quantitySelected,
  setQuantitySelected,
  isShiftPressed,
  onRowClick,
  onViewChunks,
}: KnowledgeBasesTabProps) => {
  const { t } = useTranslation();
  const tableRef = useRef<AgGridReact<unknown>>(null);
  const { setErrorData, setSuccessData, setNoticeData } = useAlertStore(
    (state) => ({
      setErrorData: state.setErrorData,
      setSuccessData: state.setSuccessData,
      setNoticeData: state.setNoticeData,
    }),
  );

  const examples = useFlowsManagerStore((state) => state.examples);
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folderIdUrl = folderId ?? myCollectionId;

  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const createTriggerRef = useRef<HTMLElement | null>(null);
  const deleteFocusKbNameRef = useRef<string | null>(null);
  const bulkDeleteTriggerRef = useRef<HTMLElement | null>(null);

  const captureActiveElement = () =>
    document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;

  const focusRowActionsForKb = (kbName: string | null) => {
    if (!kbName) return;
    // Prefer the actions trigger whose aria-label includes the KB name.
    // AG Grid may remount cell renderers while a dialog is open, so always
    // re-query the live DOM instead of focusing a stale element reference.
    const triggers = document.querySelectorAll<HTMLElement>(
      '[data-testid="kb-row-actions-trigger"]',
    );
    for (const trigger of triggers) {
      const label = trigger.getAttribute("aria-label") ?? "";
      if (label.includes(kbName)) {
        trigger.focus();
        return;
      }
    }
    triggers[0]?.focus();
  };

  const {
    data: knowledgeBases,
    isLoading,
    error,
    refetch,
  } = useGetKnowledgeBases();

  // --- Extracted hooks ---

  const { pollingRef } = useKnowledgeBasePolling({
    knowledgeBases,
    tableRef,
    onStatusChange: (transitions) => {
      for (const { kb, previousStatus } of transitions) {
        if (kb.status === "failed" && previousStatus !== "failed") {
          setErrorData({
            title: t("knowledge.ingestionFailed", { name: kb.name }),
            list: kb.failure_reason ? [kb.failure_reason] : undefined,
          });
        } else if (kb.status === "ready" && previousStatus === "ingesting") {
          // KB.status doesn't distinguish a fully-successful run from a
          // partial one (some files skipped/failed), so look at the
          // most recent run for an accurate, run-scoped message.
          notifyOnIngestionFinished(kb.dir_name, kb.name, kb.chunks).then(
            ({ kind, title }) => {
              if (kind === "notice") {
                setNoticeData({ title });
              } else {
                setSuccessData({
                  title: t("knowledge.ingestionComplete", {
                    name: kb.name,
                    chunks: kb.chunks,
                  }),
                });
              }
            },
          );
        }
      }
    },
  });

  const clearSelection = () => {
    setQuantitySelected(0);
    setSelectedFiles([]);
  };

  const actions = useKnowledgeBaseActions({
    refetch,
    selectedFiles,
    clearSelection,
  });

  const { captureSubmit, applyOptimisticUpdate } = useOptimisticKnowledgeBase();

  // --- Event handlers ---

  const handleCreateKnowledge = async () => {
    const knowledgeBasesExample = examples.find(
      (example) => example.name === "Knowledge Ingestion",
    );

    if (knowledgeBasesExample && knowledgeBasesExample.data) {
      updateIds(knowledgeBasesExample.data);
      addFlow({ flow: knowledgeBasesExample }).then((id) => {
        navigate(`/flow/${id}/folder/${folderIdUrl}`);
      });
      track("New Flow Created", {
        template: `${knowledgeBasesExample.name} Template`,
      });
    }
  };

  const handleRowClick = (event: RowClickedEvent) => {
    const clickedElement = event.event?.target as HTMLElement;
    if (clickedElement && !clickedElement.closest("button") && onRowClick) {
      onRowClick(event.data);
    }
  };

  // AG Grid navigates cell-by-cell and never focuses the action button inside a
  // cell, so keyboard users can't open the row actions menu. Open it when
  // Enter/Space is pressed while the actions cell is focused (WCAG 2.1.1).
  const handleCellKeyDown = (event: CellKeyDownEvent<KnowledgeBaseInfo>) => {
    const keyboardEvent = event.event as KeyboardEvent | undefined;
    if (!keyboardEvent) return;

    if (event.column?.getColId() === "actions") {
      if (keyboardEvent.key !== "Enter" && keyboardEvent.key !== " ") {
        return;
      }
      const target = keyboardEvent.target as HTMLElement | null;
      // The key was already re-dispatched onto the trigger button: let Radix's
      // own keyboard handler open the menu and don't recurse.
      if (target?.tagName === "BUTTON") {
        return;
      }
      const actionsButton = target
        ?.closest?.('[role="gridcell"]')
        ?.querySelector<HTMLElement>('[data-testid="kb-row-actions-trigger"]');
      if (!actionsButton) {
        return;
      }
      keyboardEvent.preventDefault();
      actionsButton.focus();
      actionsButton.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: keyboardEvent.key,
          bubbles: true,
          cancelable: true,
        }),
      );
      return;
    }

    if (keyboardEvent.key !== "Enter") return;
    const target = keyboardEvent.target as HTMLElement | null;
    if (target?.closest("button, a, input, [role='menuitem']")) return;

    if (onRowClick && event.data) {
      keyboardEvent.preventDefault();
      onRowClick(event.data);
    }
  };

  const handleAddSources = (
    knowledgeBase: Parameters<typeof actions.handleAddSources>[0],
  ) => {
    createTriggerRef.current = captureActiveElement();
    actions.handleAddSources(knowledgeBase);
    setIsUploadModalOpen(true);
  };

  const handleOpenCreateModal = () => {
    createTriggerRef.current = captureActiveElement();
    setIsUploadModalOpen(true);
  };

  const handleOpenBulkDeleteModal = () => {
    bulkDeleteTriggerRef.current = captureActiveElement();
    actions.setIsBulkDeleteModalOpen(true);
  };

  const handleDeleteWithFocus = (
    knowledgeBase: Parameters<typeof actions.handleDelete>[0],
    _focusTarget?: HTMLElement | null,
  ) => {
    deleteFocusKbNameRef.current = knowledgeBase.name;
    actions.handleDelete(knowledgeBase);
  };

  const existingKnowledgeBaseData = useMemo(() => {
    if (!actions.knowledgeBaseForAddSources) return undefined;
    return {
      name: actions.knowledgeBaseForAddSources.dir_name,
      embeddingProvider: actions.knowledgeBaseForAddSources.embedding_provider,
      embeddingModel: actions.knowledgeBaseForAddSources.embedding_model,
      chunkSize: actions.knowledgeBaseForAddSources.chunk_size,
      chunkOverlap: actions.knowledgeBaseForAddSources.chunk_overlap,
      separator: actions.knowledgeBaseForAddSources.separator,
      columnConfig: actions.knowledgeBaseForAddSources.column_config,
      backendType: actions.knowledgeBaseForAddSources.backend_type,
      backendConfig: actions.knowledgeBaseForAddSources.backend_config,
    };
  }, [actions.knowledgeBaseForAddSources]);

  const sortedKnowledgeBases = useMemo(
    () =>
      knowledgeBases
        ? [...knowledgeBases].sort((a, b) =>
            a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
          )
        : [],
    [knowledgeBases],
  );

  const columnDefs = createKnowledgeBaseColumns(
    {
      onViewChunks: onViewChunks ?? onRowClick,
      onDelete: handleDeleteWithFocus,
      onAddSources: handleAddSources,
      onStopIngestion: actions.handleStopIngestion,
    },
    t,
  );

  // --- Error handling ---

  if (error) {
    setErrorData({
      title: t("knowledge.failedToLoad"),
      list: [error?.message || t("knowledge.unknownError")],
    });
  }

  // --- Render ---

  return (
    <DataTableTab<KnowledgeBaseInfo>
      columnDefs={columnDefs}
      rowData={sortedKnowledgeBases}
      isLoading={isLoading || !knowledgeBases || !Array.isArray(knowledgeBases)}
      loadingState={
        <div className="flex flex-1 w-full flex-col items-center justify-center gap-3">
          <Loading size={36} />
          <span className="text-sm text-muted-foreground pt-3">
            {t("knowledge.loadingKnowledgeBases")}
          </span>
        </div>
      }
      emptyState={
        <KnowledgeBaseEmptyState
          handleCreateKnowledge={handleCreateKnowledge}
        />
      }
      searchPlaceholder={t("knowledge.searchPlaceholder")}
      searchInputTestId="search-kb-input"
      searchInputAriaLabel={t("knowledge.searchKnowledgeBases")}
      quickFilterText={quickFilterText}
      setQuickFilterText={setQuickFilterText}
      toolbarActions={
        quantitySelected > 0 ? (
          <Button
            variant="destructive"
            className="flex items-center gap-2 font-semibold ml-4"
            onClick={handleOpenBulkDeleteModal}
          >
            <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
            {t("knowledge.deleteSelected", { count: quantitySelected })}
          </Button>
        ) : (
          <Button
            className="flex items-center gap-2 font-semibold ml-4"
            onClick={handleOpenCreateModal}
          >
            <ForwardedIconComponent name="Plus" className="h-4 w-4" />
            {t("knowledge.addKnowledge")}
          </Button>
        )
      }
      setSelectedRows={setSelectedFiles}
      setQuantitySelected={setQuantitySelected}
      quantitySelected={quantitySelected}
      isShiftPressed={isShiftPressed}
      tableRef={tableRef}
      tableClassName="ag-knowledge-table"
      onRowClicked={handleRowClick}
      onCellKeyDown={handleCellKeyDown}
      getRowId={(params) => params.data.dir_name}
      gridOptions={{
        paginationAutoPageSize: true,
        isRowSelectable: (rowNode) => !isBusyStatus(rowNode.data?.status),
      }}
    >
      <DeleteConfirmationModal
        open={actions.isDeleteModalOpen}
        setOpen={actions.setIsDeleteModalOpen}
        onConfirm={actions.confirmDelete}
        description={`knowledge base "${actions.knowledgeBaseToDelete?.name || ""}"`}
        note={t("knowledge.thisActionCannotBeUndone")}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const kbName = deleteFocusKbNameRef.current;
          deleteFocusKbNameRef.current = null;
          // AG Grid may remount the cell renderer while the dialog is open,
          // so re-query the live trigger instead of focusing a stale node.
          requestAnimationFrame(() => focusRowActionsForKb(kbName));
        }}
      />

      <DeleteConfirmationModal
        open={actions.isBulkDeleteModalOpen}
        setOpen={actions.setIsBulkDeleteModalOpen}
        onConfirm={actions.confirmBulkDelete}
        description={`${actions.deletableSelected.length} knowledge base(s)`}
        note={
          actions.deletableSelected.length < selectedFiles.length
            ? `${selectedFiles.length - actions.deletableSelected.length} ingesting knowledge base(s) will be skipped. ${t("knowledge.thisActionCannotBeUndone")}`
            : t("knowledge.thisActionCannotBeUndone")
        }
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          bulkDeleteTriggerRef.current?.focus();
          bulkDeleteTriggerRef.current = null;
        }}
      />

      <KnowledgeBaseUploadModal
        open={isUploadModalOpen}
        setOpen={(open) => {
          setIsUploadModalOpen(open);
          if (!open) {
            const startedPolling = applyOptimisticUpdate();
            if (startedPolling) {
              // Files were submitted — trust the optimistic "ingesting" status.
              // Polling will sync the real status; an immediate refetch would
              // race with the fire-and-forget ingest POST and overwrite our
              // optimistic update with "empty".
              pollingRef.current = true;
            } else {
              // No files — safe to refetch immediately (server returns "empty").
              refetch();
            }
            actions.setKnowledgeBaseForAddSources(null);
          }
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          createTriggerRef.current?.focus();
          createTriggerRef.current = null;
        }}
        onSubmit={captureSubmit}
        existingKnowledgeBase={existingKnowledgeBaseData}
        existingKnowledgeBaseNames={
          knowledgeBases?.map((kb) => kb.dir_name) ?? []
        }
      />
    </DataTableTab>
  );
};

export default KnowledgeBasesTab;
