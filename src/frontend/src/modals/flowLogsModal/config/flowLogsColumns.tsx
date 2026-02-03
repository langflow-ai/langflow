import type { ColDef } from "ag-grid-community";
import { Badge } from "@/components/ui/badge";

const baseCellClass =
  "flex items-center truncate cursor-default leading-normal";

const clickableCellClass =
  "flex items-center truncate cursor-pointer leading-normal hover:text-primary hover:underline";

const formatObjectValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

export function createFlowLogsColumns(): ColDef[] {
  return [
    {
      headerName: "Timestamp",
      field: "timestamp",
      flex: 1,
      minWidth: 160,
      filter: false,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
    },
    {
      headerName: "Component",
      field: "vertex_id",
      flex: 1,
      minWidth: 180,
      filter: false,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
    },
    {
      headerName: "Inputs",
      field: "inputs",
      flex: 1.2,
      minWidth: 150,
      filter: false,
      sortable: false,
      editable: false,
      cellClass: clickableCellClass,
      valueGetter: (params) => formatObjectValue(params.data?.inputs),
    },
    {
      headerName: "Outputs",
      field: "outputs",
      flex: 1.2,
      minWidth: 150,
      filter: false,
      sortable: false,
      editable: false,
      cellClass: clickableCellClass,
      valueGetter: (params) => formatObjectValue(params.data?.outputs),
    },
    {
      headerName: "Status",
      field: "status",
      flex: 0.6,
      minWidth: 100,
      filter: false,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      cellRenderer: (params: { value: string | null | undefined }) => {
        const status = params.value ?? "unknown";
        const isSuccess = status === "success";
        const isError = status === "error";

        return (
          <div className="flex items-center">
            <Badge
              variant={
                isSuccess
                  ? "successStatic"
                  : isError
                    ? "errorStatic"
                    : "secondaryStatic"
              }
              size="md"
            >
              {status}
            </Badge>
          </div>
        );
      },
    },
  ];
}
