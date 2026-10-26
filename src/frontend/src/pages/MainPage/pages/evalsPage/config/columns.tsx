import type { ColDef } from "ag-grid-community";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type {
  Dataset,
  DatasetItem,
  Evaluation,
} from "@/controllers/API/queries/evals/types";
import RowActionsMenu, { type RowAction } from "../components/RowActionsMenu";
import RunStatusBadge from "../components/RunStatusBadge";
import { formatPercent, formatRunDate } from "../utils/format";

type TranslateFn = (key: string, options?: Record<string, unknown>) => string;

/** The cell classes the Knowledge and Files tables use, so rows read the same. */
const MUTED_CELL =
  "text-muted-foreground cursor-pointer select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none";
const PRIMARY_CELL =
  "text-primary group-[.no-select-cells]:cursor-pointer group-[.no-select-cells]:select-none";

function nameCell(icon: string) {
  return (params: { value: string }) => (
    <div className="flex min-w-0 items-center gap-3 pl-1">
      <ForwardedIconComponent
        name={icon}
        aria-hidden="true"
        className="h-5 w-5 shrink-0 text-muted-foreground"
      />
      <span className="truncate" title={params.value}>
        {params.value}
      </span>
    </div>
  );
}

function actionsColumn<T>(
  label: (row: T) => string,
  actions: (row: T) => RowAction[],
): ColDef {
  return {
    headerName: "",
    colId: "actions",
    width: 64,
    sortable: false,
    resizable: false,
    editable: false,
    cellRenderer: (params: { data: T }) => (
      <RowActionsMenu
        label={label(params.data)}
        actions={actions(params.data)}
        testId="evals-row-actions"
      />
    ),
  };
}

export function datasetColumns(
  t: TranslateFn,
  handlers: {
    onOpen: (dataset: Dataset) => void;
    onDuplicate: (dataset: Dataset) => void;
    onDelete: (dataset: Dataset) => void;
  },
): ColDef[] {
  return [
    {
      headerName: t("evals.datasets.name"),
      field: "name",
      flex: 2,
      minWidth: 220,
      sortable: true,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      cellClass: PRIMARY_CELL,
      cellRenderer: nameCell("Table"),
    },
    {
      headerName: t("evals.datasets.description"),
      field: "description",
      flex: 3,
      sortable: false,
      cellClass: MUTED_CELL,
      valueFormatter: (params) => params.value ?? "",
    },
    {
      headerName: t("evals.datasets.items"),
      field: "item_count",
      width: 110,
      sortable: true,
      cellClass: MUTED_CELL,
    },
    {
      headerName: t("evals.updated"),
      field: "updated_at",
      flex: 1.2,
      sortable: true,
      cellClass: MUTED_CELL,
      valueFormatter: (params) => formatRunDate(params.value),
    },
    actionsColumn<Dataset>(
      (dataset) => t("evals.moreActionsFor", { name: dataset.name }),
      (dataset) => [
        {
          label: t("evals.open"),
          icon: "ArrowRight",
          onSelect: () => handlers.onOpen(dataset),
        },
        {
          label: t("evals.duplicate"),
          icon: "Copy",
          onSelect: () => handlers.onDuplicate(dataset),
        },
        {
          label: t("evals.delete"),
          icon: "Trash2",
          destructive: true,
          onSelect: () => handlers.onDelete(dataset),
        },
      ],
    ),
  ];
}

export function evaluationColumns(
  t: TranslateFn,
  handlers: {
    onOpen: (evaluation: Evaluation) => void;
    onDelete: (evaluation: Evaluation) => void;
  },
): ColDef[] {
  const deletedLabel = (key: string) => (
    <span className="text-muted-foreground">{t(key)}</span>
  );
  return [
    {
      headerName: t("evals.evaluations.name"),
      field: "name",
      flex: 2,
      minWidth: 220,
      sortable: true,
      checkboxSelection: false,
      headerCheckboxSelection: false,
      cellClass: PRIMARY_CELL,
      cellRenderer: nameCell("FlaskConical"),
    },
    {
      headerName: t("evals.evaluations.flow"),
      field: "flow_name",
      flex: 1.5,
      sortable: true,
      cellClass: MUTED_CELL,
      cellRenderer: (params: { value: string | null }) =>
        params.value ?? deletedLabel("evals.evaluations.flowDeleted"),
    },
    {
      headerName: t("evals.evaluations.dataset"),
      field: "dataset_name",
      flex: 1.5,
      sortable: true,
      cellClass: MUTED_CELL,
      cellRenderer: (params: { value: string | null }) =>
        params.value ?? deletedLabel("evals.evaluations.datasetDeleted"),
    },
    {
      headerName: t("evals.evaluations.lastRun"),
      colId: "last_run",
      flex: 1.6,
      sortable: false,
      cellClass: MUTED_CELL,
      cellRenderer: (params: { data: Evaluation }) => {
        const run = params.data.last_run;
        if (!run) return deletedLabel("evals.evaluations.neverRun");
        return (
          <div className="flex items-center gap-2">
            <RunStatusBadge status={run.status} />
            <span>{formatRunDate(run.created_at)}</span>
          </div>
        );
      },
    },
    {
      headerName: t("evals.passRate"),
      colId: "pass_rate",
      width: 120,
      sortable: false,
      cellClass: MUTED_CELL,
      valueGetter: (params) =>
        formatPercent(params.data?.last_run?.summary?.pass_rate),
    },
    actionsColumn<Evaluation>(
      (evaluation) => t("evals.moreActionsFor", { name: evaluation.name }),
      (evaluation) => [
        {
          label: t("evals.open"),
          icon: "ArrowRight",
          onSelect: () => handlers.onOpen(evaluation),
        },
        {
          label: t("evals.delete"),
          icon: "Trash2",
          destructive: true,
          onSelect: () => handlers.onDelete(evaluation),
        },
      ],
    ),
  ];
}

export function datasetItemColumns(
  t: TranslateFn,
  handlers: {
    onEdit: (item: DatasetItem) => void;
    onDelete: (item: DatasetItem) => void;
  },
): ColDef[] {
  return [
    {
      headerName: t("evals.items.input"),
      field: "input",
      flex: 3,
      minWidth: 240,
      sortable: false,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      cellClass: PRIMARY_CELL,
      tooltipField: "input",
    },
    {
      headerName: t("evals.items.expected"),
      field: "expected_output",
      flex: 2,
      sortable: false,
      cellClass: MUTED_CELL,
      tooltipField: "expected_output",
      valueFormatter: (params) => params.value ?? "—",
    },
    actionsColumn<DatasetItem>(
      () => t("evals.items.actions"),
      (item) => [
        {
          label: t("evals.items.edit"),
          icon: "Pencil",
          onSelect: () => handlers.onEdit(item),
        },
        {
          label: t("evals.delete"),
          icon: "Trash2",
          destructive: true,
          onSelect: () => handlers.onDelete(item),
        },
      ],
    ),
  ];
}
