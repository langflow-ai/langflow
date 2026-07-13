import type { RowClickedEvent, SelectionChangedEvent } from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type {
  IngestionRunInfo,
  PaginatedIngestionRunResponse,
} from "@/controllers/API/queries/knowledge-bases/use-get-ingestion-runs";
import { useGetKnowledgeBases } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import KnowledgeBaseUploadModal from "@/modals/knowledgeBaseUploadModal/KnowledgeBaseUploadModal";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { updateIds } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
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

  const handleSelectionChange = (event: SelectionChangedEvent) => {
    const selectedRows = event.api.getSelectedRows();
    setSelectedFiles(selectedRows);
    if (selectedRows.length > 0) {
      setQuantitySelected(selectedRows.length);
    } else {
      setTimeout(() => {
        setQuantitySelected(0);
      }, 300);
    }
  };

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

  const handleAddSources = (
    knowledgeBase: Parameters<typeof actions.handleAddSources>[0],
  ) => {
    actions.handleAddSources(knowledgeBase);
    setIsUploadModalOpen(true);
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
      onDelete: actions.handleDelete,
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

  if (isLoading || !knowledgeBases || !Array.isArray(knowledgeBases)) {
    return (
      <div className="flex flex-1 w-full flex-col items-center justify-center gap-3">
        <Loading size={36} />
        <span className="text-sm text-muted-foreground pt-3">
          {t("knowledge.loadingKnowledgeBases")}
        </span>
      </div>
    );
  }

  if (knowledgeBases.length === 0) {
    return (
      <KnowledgeBaseEmptyState handleCreateKnowledge={handleCreateKnowledge} />
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex justify-between">
        <div className="flex w-full xl:w-5/12">
          <Input
            icon="Search"
            data-testid="search-kb-input"
            type="text"
            placeholder={t("knowledge.searchPlaceholder")}
            className="w-full"
            value={quickFilterText || ""}
            onChange={(event) => setQuickFilterText(event.target.value)}
          />
        </div>
        {quantitySelected > 0 ? (
          <Button
            variant="destructive"
            className="flex items-center gap-2 font-semibold"
            onClick={() => actions.setIsBulkDeleteModalOpen(true)}
          >
            <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
            {t("knowledge.deleteSelected", { count: quantitySelected })}
          </Button>
        ) : (
          <Button
            className="flex items-center gap-2 font-semibold"
            onClick={() => setIsUploadModalOpen(true)}
          >
            <ForwardedIconComponent name="Plus" className="h-4 w-4" />
            {t("knowledge.addKnowledge")}
          </Button>
        )}
      </div>

      <div className="flex h-full flex-col py-4">
        <div className="relative h-full">
          <TableComponent
            rowHeight={45}
            headerHeight={45}
            cellSelection={false}
            tableOptions={{ hide_options: true }}
            suppressRowClickSelection={!isShiftPressed}
            rowSelection="multiple"
            onSelectionChanged={handleSelectionChange}
            onRowClicked={handleRowClick}
            columnDefs={columnDefs}
            rowData={sortedKnowledgeBases}
            className={cn(
              "ag-no-border ag-knowledge-table group w-full",
              isShiftPressed && quantitySelected > 0 && "no-select-cells",
            )}
            pagination
            ref={tableRef}
            quickFilterText={quickFilterText}
            getRowId={(params) => params.data.dir_name}
            gridOptions={{
              stopEditingWhenCellsLoseFocus: true,
              ensureDomOrder: true,
              colResizeDefault: "shift",
              paginationAutoPageSize: true,
              isRowSelectable: (rowNode) => !isBusyStatus(rowNode.data?.status),
            }}
          />
        </div>
      </div>

      <DeleteConfirmationModal
        open={actions.isDeleteModalOpen}
        setOpen={actions.setIsDeleteModalOpen}
        onConfirm={actions.confirmDelete}
        description={`knowledge base "${actions.knowledgeBaseToDelete?.name || ""}"`}
        note={t("knowledge.thisActionCannotBeUndone")}
      >
        <></>
      </DeleteConfirmationModal>

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
      >
        <></>
      </DeleteConfirmationModal>

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
        onSubmit={captureSubmit}
        existingKnowledgeBase={existingKnowledgeBaseData}
        existingKnowledgeBaseNames={
          knowledgeBases?.map((kb) => kb.dir_name) ?? []
        }
      />
    </div>
  );
};

export default KnowledgeBasesTab;
