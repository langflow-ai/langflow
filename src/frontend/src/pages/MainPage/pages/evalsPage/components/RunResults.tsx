import type { RowClickedEvent } from "ag-grid-community";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import DataTableTab from "@/components/core/dataTableTabComponent";
import {
  type EvaluationResult,
  type EvaluationRun,
  TERMINAL_RUN_STATUSES,
} from "@/controllers/API/queries/evals/types";
import { useGetEvaluationResults } from "@/controllers/API/queries/evals/use-evaluations";
import { resultColumns } from "../config/resultColumns";
import { EvalsEmptyState, EvalsLoadingState } from "./EvalsStates";
import ResultDetailDialog from "./ResultDetailDialog";
import ResultFilter, {
  RESULT_FILTERS,
  type ResultFilterValue,
} from "./ResultFilter";
import RunKpis from "./RunKpis";

// The table pages on the client; a run holds at most a few thousand rows.
const RESULTS_SIZE = 5000;
type Filter = ResultFilterValue;

function matches(result: EvaluationResult, filter: Filter): boolean {
  if (filter === "passed") return result.passed === true;
  if (filter === "failed") return result.passed === false && !result.error;
  if (filter === "errored") return Boolean(result.error);
  return true;
}

export default function RunResults({ run }: { run: EvaluationRun }) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [opened, setOpened] = useState<EvaluationResult | null>(null);
  const active = !TERMINAL_RUN_STATUSES.has(run.status);
  const { data, isLoading } = useGetEvaluationResults(
    {
      runId: run.id,
      size: RESULTS_SIZE,
      // The run is what polls; new rows load only when it reports progress or ends.
      progressKey: `${run.status}:${run.completed_items}`,
    },
    // Each progress step is a new key; drop the superseded snapshots of a live run at once.
    active ? { gcTime: 0 } : undefined,
  );
  const scorerNames = run.config.scorers.map((scorer) => scorer.name);
  const rows = useMemo(
    () => (data?.items ?? []).filter((result) => matches(result, filter)),
    [data, filter],
  );
  const counts = useMemo(() => {
    const all = data?.items ?? [];
    return Object.fromEntries(
      RESULT_FILTERS.map((name) => [
        name,
        all.filter((r) => matches(r, name)).length,
      ]),
    ) as Record<Filter, number>;
  }, [data]);

  return (
    <div className="flex flex-col gap-4">
      <RunKpis run={run} />
      <ResultFilter value={filter} counts={counts} onChange={setFilter} />
      <div className="flex min-h-[420px] flex-col">
        <DataTableTab<EvaluationResult>
          columnDefs={resultColumns(t, scorerNames)}
          rowData={rows}
          isLoading={isLoading}
          loadingState={
            <EvalsLoadingState label={t("evals.results.loading")} />
          }
          emptyState={
            <EvalsEmptyState
              icon={active ? "Loader2" : "ListFilter"}
              spinning={active}
              title={
                active
                  ? t("evals.results.waitingTitle")
                  : t("evals.results.noMatchTitle")
              }
              description={
                active
                  ? t("evals.results.waitingBody")
                  : t("evals.results.noMatchBody")
              }
            />
          }
          searchPlaceholder={t("evals.results.search")}
          searchInputTestId="search-results-input"
          searchInputAriaLabel={t("evals.results.search")}
          quickFilterText={search}
          setQuickFilterText={setSearch}
          toolbarActions={null}
          setSelectedRows={() => undefined}
          setQuantitySelected={() => undefined}
          quantitySelected={0}
          isShiftPressed={false}
          onRowClicked={(event: RowClickedEvent<EvaluationResult>) => {
            if (event.data) setOpened(event.data);
          }}
          getRowId={(params) => params.data.id}
          gridOptions={{ paginationAutoPageSize: true, tooltipShowDelay: 400 }}
        />
      </div>
      <ResultDetailDialog
        runId={run.id}
        result={opened}
        scorerNames={scorerNames}
        onClose={() => setOpened(null)}
      />
    </div>
  );
}
