import type { RowClickedEvent } from "ag-grid-community";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import DataTableTab from "@/components/core/dataTableTabComponent";
import { Button } from "@/components/ui/button";
import type { Evaluation } from "@/controllers/API/queries/evals/types";
import {
  useDeleteEvaluation,
  useGetEvaluations,
} from "@/controllers/API/queries/evals/use-evaluations";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useDocumentTitle } from "@/hooks/use-document-title";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import EvaluateFlowModal from "@/modals/evaluateFlowModal";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import EvalsPageShell from "./components/EvalsPageShell";
import { EvalsEmptyState, EvalsLoadingState } from "./components/EvalsStates";
import { evaluationColumns } from "./config/columns";

const LIST_SIZE = 200;

export default function EvaluationsPage() {
  const { t } = useTranslation();
  useDocumentTitle(t("evals.evaluations.title"));
  const navigate = useCustomNavigate();
  const [search, setSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Evaluation | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const newButton = (
    <Button
      className="flex items-center gap-2 font-semibold"
      onClick={() => setCreateOpen(true)}
      data-testid="new-evaluation-button"
    >
      <ForwardedIconComponent name="Plus" className="h-4 w-4" />
      {t("evals.evaluations.new")}
    </Button>
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { data, isLoading, isError } = useGetEvaluations({ size: LIST_SIZE });
  const deleteEvaluation = useDeleteEvaluation({
    onError: (error) =>
      setErrorData({
        title: t("evals.evaluations.deleteError"),
        list: extractApiErrorMessages(error),
      }),
  });
  const open = (evaluation: Evaluation) =>
    navigate(`/assets/evaluations/${evaluation.id}`);
  const columns = evaluationColumns(t, {
    onOpen: open,
    onDelete: setPendingDelete,
  });

  return (
    <EvalsPageShell
      title={t("evals.evaluations.title")}
      titleTestId="evaluations-title"
    >
      {isError ? (
        <p role="alert" className="text-sm text-destructive">
          {t("evals.loadError")}
        </p>
      ) : (
        <DataTableTab<Evaluation>
          columnDefs={columns}
          rowData={data?.items ?? []}
          isLoading={isLoading}
          loadingState={
            <EvalsLoadingState label={t("evals.evaluations.loading")} />
          }
          emptyState={
            <EvalsEmptyState
              icon="FlaskConical"
              title={t("evals.evaluations.emptyTitle")}
              description={t("evals.evaluations.emptyBody")}
              actions={newButton}
            />
          }
          searchPlaceholder={t("evals.evaluations.search")}
          searchInputTestId="search-evaluations-input"
          searchInputAriaLabel={t("evals.evaluations.search")}
          quickFilterText={search}
          setQuickFilterText={setSearch}
          toolbarActions={<div className="ml-4">{newButton}</div>}
          setSelectedRows={() => undefined}
          setQuantitySelected={() => undefined}
          quantitySelected={0}
          isShiftPressed={false}
          onRowClicked={(event: RowClickedEvent<Evaluation>) => {
            const target = event.event?.target as HTMLElement | undefined;
            if (event.data && !target?.closest("button")) open(event.data);
          }}
          getRowId={(params) => params.data.id}
          gridOptions={{ paginationAutoPageSize: true }}
        >
          {createOpen && (
            <EvaluateFlowModal open={createOpen} setOpen={setCreateOpen} />
          )}
          <DeleteConfirmationModal
            open={pendingDelete !== null}
            setOpen={(next) => !next && setPendingDelete(null)}
            description={t("evals.evaluations.deleteDescription")}
            onConfirm={() => {
              if (pendingDelete) {
                deleteEvaluation.mutate({ evaluationId: pendingDelete.id });
              }
              setPendingDelete(null);
            }}
          />
        </DataTableTab>
      )}
    </EvalsPageShell>
  );
}
