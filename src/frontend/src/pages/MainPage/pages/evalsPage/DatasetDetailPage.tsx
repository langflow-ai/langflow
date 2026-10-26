import type { RowClickedEvent } from "ag-grid-community";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import DataTableTab from "@/components/core/dataTableTabComponent";
import { Button } from "@/components/ui/button";
import type { DatasetItem } from "@/controllers/API/queries/evals/types";
import {
  useDeleteDatasetItems,
  useGetDataset,
  useGetDatasetItems,
} from "@/controllers/API/queries/evals/use-datasets";
import { exportUrl } from "@/controllers/API/queries/evals/use-evaluations";
import { useDocumentTitle } from "@/hooks/use-document-title";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import BackLink from "./components/BackLink";
import CsvImportDialog from "./components/CsvImportDialog";
import DatasetItemDialog from "./components/DatasetItemDialog";
import EvalsPageShell from "./components/EvalsPageShell";
import { EvalsEmptyState, EvalsLoadingState } from "./components/EvalsStates";
import { datasetItemColumns } from "./config/columns";
import { useShiftKey } from "./hooks/use-shift-key";
import { downloadCsv } from "./utils/download-csv";
import { formatRunDate } from "./utils/format";

// The table pages on the client; a dataset holds at most a few thousand rows.
const ITEMS_SIZE = 5000;

export default function DatasetDetailPage() {
  const { t } = useTranslation();
  const { datasetId = "" } = useParams();
  const isShiftPressed = useShiftKey();
  const [search, setSearch] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<DatasetItem | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [selected, setSelected] = useState<DatasetItem[]>([]);
  const [quantitySelected, setQuantitySelected] = useState(0);
  const [pendingDelete, setPendingDelete] = useState<DatasetItem[]>([]);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const onError = (title: string) => (error: unknown) =>
    setErrorData({ title, list: extractApiErrorMessages(error) });
  const { data: dataset, isError } = useGetDataset({ datasetId });
  const { data: items, isLoading } = useGetDatasetItems({
    datasetId,
    size: ITEMS_SIZE,
  });
  const deleteItems = useDeleteDatasetItems(
    { datasetId },
    { onError: onError(t("evals.items.deleteError")) },
  );
  useDocumentTitle(dataset?.name ?? t("evals.datasets.title"));

  const openEditor = (item: DatasetItem | null) => {
    setEditing(item);
    setEditorOpen(true);
  };
  const handleExport = () =>
    downloadCsv(exportUrl("dataset", datasetId), "dataset.csv").catch(
      onError(t("evals.exportError")),
    );
  const handleConfirmDeleteItems = () => {
    deleteItems.mutate({ ids: pendingDelete.map((item) => item.id) });
    setPendingDelete([]);
    setSelected([]);
    setQuantitySelected(0);
  };

  const importButton = (
    <Button
      variant="outline"
      className="flex items-center gap-2 font-semibold"
      onClick={() => setImportOpen(true)}
      data-testid="csv-import-button"
    >
      <ForwardedIconComponent name="FileUp" className="h-4 w-4" />
      {t("evals.csv.title")}
    </Button>
  );
  const addButton = (
    <Button
      className="flex items-center gap-2 font-semibold"
      onClick={() => openEditor(null)}
      data-testid="add-item-button"
    >
      <ForwardedIconComponent name="Plus" className="h-4 w-4" />
      {t("evals.items.add")}
    </Button>
  );

  return (
    <EvalsPageShell
      title={dataset?.name ?? t("evals.datasets.title")}
      titleTestId="dataset-detail-title"
      back={<BackLink to="/assets/datasets" label={t("evals.datasets.back")} />}
      meta={
        dataset && (
          <p className="text-sm text-muted-foreground">
            {dataset.description ? `${dataset.description} · ` : ""}
            {t("evals.datasets.meta", {
              count: dataset.item_count,
              date: formatRunDate(dataset.updated_at),
            })}
          </p>
        )
      }
    >
      {isError ? (
        <p role="alert" className="text-sm text-destructive">
          {t("evals.loadError")}
        </p>
      ) : (
        <DataTableTab<DatasetItem>
          columnDefs={datasetItemColumns(t, {
            onEdit: openEditor,
            onDelete: (item) => setPendingDelete([item]),
          })}
          rowData={items?.items ?? []}
          isLoading={isLoading}
          loadingState={<EvalsLoadingState label={t("evals.items.loading")} />}
          emptyState={
            <EvalsEmptyState
              icon="ListPlus"
              title={t("evals.items.emptyTitle")}
              description={t("evals.items.emptyBody")}
              actions={
                <>
                  {importButton}
                  {addButton}
                </>
              }
            />
          }
          searchPlaceholder={t("evals.items.search")}
          searchInputTestId="search-items-input"
          searchInputAriaLabel={t("evals.items.search")}
          quickFilterText={search}
          setQuickFilterText={setSearch}
          toolbarActions={
            <div className="ml-4 flex items-center gap-2">
              {quantitySelected > 0 ? (
                <Button
                  variant="destructive"
                  className="flex items-center gap-2 font-semibold"
                  onClick={() => setPendingDelete(selected)}
                >
                  <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
                  {t("evals.deleteSelected", { count: quantitySelected })}
                </Button>
              ) : (
                <>
                  <Button
                    variant="ghost"
                    className="flex items-center gap-2"
                    onClick={handleExport}
                    data-testid="dataset-export-button"
                  >
                    <ForwardedIconComponent
                      name="Download"
                      className="h-4 w-4"
                    />
                    {t("evals.export")}
                  </Button>
                  {importButton}
                  {addButton}
                </>
              )}
            </div>
          }
          setSelectedRows={setSelected}
          setQuantitySelected={setQuantitySelected}
          quantitySelected={quantitySelected}
          isShiftPressed={isShiftPressed}
          onRowClicked={(event: RowClickedEvent<DatasetItem>) => {
            const target = event.event?.target as HTMLElement | undefined;
            if (event.data && !target?.closest("button, input")) {
              openEditor(event.data);
            }
          }}
          getRowId={(params) => params.data.id}
          gridOptions={{ paginationAutoPageSize: true, tooltipShowDelay: 400 }}
        >
          <DatasetItemDialog
            datasetId={datasetId}
            open={editorOpen}
            setOpen={setEditorOpen}
            item={editing}
          />
          <CsvImportDialog
            datasetId={datasetId}
            open={importOpen}
            setOpen={setImportOpen}
          />
          <DeleteConfirmationModal
            open={pendingDelete.length > 0}
            setOpen={(next) => !next && setPendingDelete([])}
            description={t("evals.items.deleteDescription", {
              count: pendingDelete.length,
            })}
            onConfirm={handleConfirmDeleteItems}
          />
        </DataTableTab>
      )}
    </EvalsPageShell>
  );
}
