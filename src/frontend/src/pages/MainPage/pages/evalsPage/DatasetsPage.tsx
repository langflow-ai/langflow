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
import DatasetExamples from "./components/DatasetExamples";
import EvalsPageShell from "./components/EvalsPageShell";
import { EvalsEmptyState, EvalsLoadingState } from "./components/EvalsStates";
import EvalsTabs from "./components/EvalsTabs";
import ExamplesMenu from "./components/ExamplesMenu";
import ImportCsvButton from "./components/ImportCsvButton";
import { datasetColumns } from "./config/columns";
import { useQuickCreateDataset } from "./hooks/use-quick-create-dataset";
import { useShiftKey } from "./hooks/use-shift-key";
import { datasetNameFromFile } from "./utils/unique-name";

const LIST_SIZE = 200;

export default function DatasetsPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("evals.datasets.title"));
  const navigate = useCustomNavigate();
  const isShiftPressed = useShiftKey();
  const [search, setSearch] = useState("");
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
  const quickCreate = useQuickCreateDataset(
    (data?.items ?? []).map((dataset) => dataset.name),
  );
  const [creating, setCreating] = useState<"blank" | "csv" | null>(null);
  // The dataset page opens the column mapping for this file as soon as it loads.
  const createAndOpen = async (kind: "blank" | "csv", file?: File) => {
    setCreating(kind);
    try {
      const dataset = await quickCreate.createUnique(
        file ? datasetNameFromFile(file.name) : t("evals.datasets.untitled"),
      );
      if (dataset) {
        navigate(`/assets/datasets/${dataset.id}`, {
          state: file ? { importFile: file } : { rename: true },
        });
      }
    } finally {
      setCreating(null);
    }
  };

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

  const createButtons = (
    <>
      <ImportCsvButton
        testId="import-dataset-button"
        loading={creating === "csv"}
        onFile={(file) => void createAndOpen("csv", file)}
      />
      <Button
        className="flex items-center gap-2 font-semibold"
        loading={creating === "blank"}
        onClick={() => void createAndOpen("blank")}
        data-testid="new-dataset-button"
      >
        <ForwardedIconComponent name="Plus" className="h-4 w-4" />
        {t("evals.datasets.new")}
      </Button>
    </>
  );

  return (
    <EvalsPageShell
      title={t("evals.evaluations.title")}
      titleTestId="datasets-title"
      tabs={<EvalsTabs active="datasets" />}
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
              actions={
                <div className="flex w-full flex-col items-center gap-8">
                  <div className="flex gap-2">{createButtons}</div>
                  <DatasetExamples />
                </div>
              }
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
                <>
                  <ExamplesMenu />
                  {createButtons}
                </>
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
