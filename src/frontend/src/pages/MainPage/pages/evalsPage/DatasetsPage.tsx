import type { RowClickedEvent } from "ag-grid-community";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import DataTableTab from "@/components/core/dataTableTabComponent";
import { Button } from "@/components/ui/button";
import type { Dataset } from "@/controllers/API/queries/evals/types";
import {
  useDeleteDataset,
  useDuplicateDataset,
  useGetDatasets,
} from "@/controllers/API/queries/evals/use-datasets";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useDocumentTitle } from "@/hooks/use-document-title";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import CreateDatasetDialog from "./components/CreateDatasetDialog";
import EvalsPageShell from "./components/EvalsPageShell";
import { EvalsEmptyState, EvalsLoadingState } from "./components/EvalsStates";
import { datasetColumns } from "./config/columns";
import { useShiftKey } from "./hooks/use-shift-key";

const LIST_SIZE = 200;

export default function DatasetsPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("evals.datasets.title"));
  const navigate = useCustomNavigate();
  const isShiftPressed = useShiftKey();
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<Dataset[]>([]);
  const [quantitySelected, setQuantitySelected] = useState(0);
  const [pendingDelete, setPendingDelete] = useState<Dataset[]>([]);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const onError = (title: string) => (error: unknown) =>
    setErrorData({ title, list: extractApiErrorMessages(error) });
  const { data, isLoading, isError } = useGetDatasets({ size: LIST_SIZE });
  // Failures are reported once for the whole batch, below.
  const deleteDataset = useDeleteDataset();
  const duplicateDataset = useDuplicateDataset({
    onError: onError(t("evals.datasets.duplicateError")),
  });
  const open = (dataset: Dataset) => navigate(`/assets/datasets/${dataset.id}`);

  const handleConfirmDelete = async () => {
    try {
      const outcomes = await Promise.allSettled(
        pendingDelete.map((dataset) =>
          deleteDataset.mutateAsync({ datasetId: dataset.id }),
        ),
      );
      const failures = outcomes.filter(
        (outcome): outcome is PromiseRejectedResult =>
          outcome.status === "rejected",
      );
      if (failures.length > 0) {
        setErrorData({
          title:
            failures.length === outcomes.length
              ? t("evals.datasets.deleteError")
              : t("evals.datasets.deletePartialError"),
          list: failures.flatMap((failure) =>
            extractApiErrorMessages(failure.reason),
          ),
        });
      }
    } finally {
      setPendingDelete([]);
      setSelected([]);
      setQuantitySelected(0);
    }
  };

  const columns = datasetColumns(t, {
    onOpen: open,
    onDuplicate: (dataset) =>
      duplicateDataset.mutate({ datasetId: dataset.id }),
    onDelete: (dataset) => setPendingDelete([dataset]),
  });

  const newButton = (
    <Button
      className="flex items-center gap-2 font-semibold"
      onClick={() => setCreateOpen(true)}
      data-testid="new-dataset-button"
    >
      <ForwardedIconComponent name="Plus" className="h-4 w-4" />
      {t("evals.datasets.new")}
    </Button>
  );

  return (
    <EvalsPageShell
      title={t("evals.datasets.title")}
      titleTestId="datasets-title"
    >
      {isError ? (
        <p role="alert" className="text-sm text-destructive">
          {t("evals.loadError")}
        </p>
      ) : (
        <DataTableTab<Dataset>
          columnDefs={columns}
          rowData={data?.items ?? []}
          isLoading={isLoading}
          loadingState={
            <EvalsLoadingState label={t("evals.datasets.loading")} />
          }
          emptyState={
            <EvalsEmptyState
              icon="Table"
              title={t("evals.datasets.emptyTitle")}
              description={t("evals.datasets.emptyBody")}
              actions={newButton}
            />
          }
          searchPlaceholder={t("evals.datasets.search")}
          searchInputTestId="search-datasets-input"
          searchInputAriaLabel={t("evals.datasets.search")}
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
                newButton
              )}
            </div>
          }
          setSelectedRows={setSelected}
          setQuantitySelected={setQuantitySelected}
          quantitySelected={quantitySelected}
          isShiftPressed={isShiftPressed}
          onRowClicked={(event: RowClickedEvent<Dataset>) => {
            const target = event.event?.target as HTMLElement | undefined;
            if (event.data && !target?.closest("button, input"))
              open(event.data);
          }}
          getRowId={(params) => params.data.id}
          gridOptions={{ paginationAutoPageSize: true }}
        >
          <CreateDatasetDialog
            open={createOpen}
            setOpen={setCreateOpen}
            onCreated={open}
          />
          <DeleteConfirmationModal
            open={pendingDelete.length > 0}
            setOpen={(next) => !next && setPendingDelete([])}
            description={t("evals.datasets.deleteDescription")}
            onConfirm={handleConfirmDelete}
          />
        </DataTableTab>
      )}
    </EvalsPageShell>
  );
}
