import type { ColDef } from "ag-grid-community";
import type { EvaluationResult } from "@/controllers/API/queries/evals/types";
import PassedBadge from "../components/PassedBadge";
import {
  formatDuration,
  formatScore,
  formatTokenCount,
  formatUsd,
} from "../utils/format";

type TranslateFn = (key: string, options?: Record<string, unknown>) => string;

const MUTED_CELL = "text-muted-foreground cursor-pointer select-text";
const PRIMARY_CELL = "text-primary cursor-pointer select-text";

function rowCost(result: EvaluationResult): number | null {
  if (result.cost_flow === null && result.cost_judge === null) return null;
  return (result.cost_flow ?? 0) + (result.cost_judge ?? 0);
}

export function resultColumns(t: TranslateFn, scorerNames: string[]): ColDef[] {
  return [
    {
      headerName: "#",
      colId: "position",
      width: 70,
      checkboxSelection: false,
      headerCheckboxSelection: false,
      sortable: true,
      cellClass: MUTED_CELL,
      valueGetter: (params) => (params.data?.position ?? 0) + 1,
    },
    {
      headerName: t("evals.items.input"),
      field: "input",
      flex: 2,
      minWidth: 160,
      cellClass: PRIMARY_CELL,
      tooltipField: "input",
    },
    {
      headerName: t("evals.items.expected"),
      field: "expected_output",
      flex: 1.5,
      minWidth: 140,
      cellClass: MUTED_CELL,
      tooltipField: "expected_output",
      valueFormatter: (params) => params.value ?? "—",
    },
    {
      headerName: t("evals.results.actual"),
      colId: "actual",
      flex: 2,
      minWidth: 180,
      cellClass: PRIMARY_CELL,
      valueGetter: (params) => params.data?.error ?? params.data?.actual_output,
      cellClassRules: {
        "text-destructive": (params) => Boolean(params.data?.error),
      },
      tooltipValueGetter: (params) => params.value,
    },
    ...scorerNames.map<ColDef>((name) => ({
      headerName: t(`evals.scorers.${name}`, { defaultValue: name }),
      colId: `score-${name}`,
      width: 120,
      sortable: true,
      type: "rightAligned",
      cellClass: MUTED_CELL,
      valueGetter: (params) => params.data?.scores?.[name]?.value ?? null,
      valueFormatter: (params) => formatScore(params.value),
    })),
    {
      headerName: t("evals.results.passedColumn"),
      field: "passed",
      width: 120,
      sortable: true,
      cellRenderer: (params: { data: EvaluationResult }) => (
        <PassedBadge passed={params.data.passed} />
      ),
    },
    {
      headerName: t("evals.results.duration"),
      field: "duration_ms",
      width: 110,
      sortable: true,
      type: "rightAligned",
      cellClass: MUTED_CELL,
      valueFormatter: (params) => formatDuration(params.value),
    },
    {
      headerName: t("evals.tokens"),
      colId: "tokens",
      width: 100,
      sortable: true,
      type: "rightAligned",
      cellClass: MUTED_CELL,
      valueGetter: (params) =>
        (params.data?.tokens_flow ?? 0) + (params.data?.tokens_judge ?? 0) ||
        null,
      valueFormatter: (params) => formatTokenCount(params.value),
    },
    {
      headerName: t("evals.cost"),
      colId: "cost",
      width: 130,
      sortable: true,
      type: "rightAligned",
      cellClass: MUTED_CELL,
      valueGetter: (params) => (params.data ? rowCost(params.data) : null),
      valueFormatter: (params) => formatUsd(params.value),
    },
  ];
}
