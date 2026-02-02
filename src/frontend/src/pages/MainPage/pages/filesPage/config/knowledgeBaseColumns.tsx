import type { ColDef } from "ag-grid-community";
import { formatFileSize } from "@/utils/stringManipulation";
import {
  formatAverageChunkSize,
  formatNumber,
} from "../utils/knowledgeBaseUtils";

export const createKnowledgeBaseColumns = (): ColDef[] => {
  const baseCellClass =
    "text-muted-foreground cursor-pointer select-text group-[.no-select-cells]:cursor-default group-[.no-select-cells]:select-none";

  return [
    {
      headerName: "Source",
      field: "name",
      flex: 2,
      sortable: true,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      editable: false,
      cellClass: baseCellClass,
    },
    {
      headerName: "Size",
      field: "size",
      flex: 1,
      sortable: false,
      valueFormatter: (params) => formatFileSize(params.value),
      editable: false,
      cellClass: baseCellClass,
    },
    {
      headerName: "Type",
      field: "type",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueGetter: (params) => params.data.type || "—",
    },
    {
      headerName: "Owner",
      field: "owner",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueGetter: (params) => params.data.owner || "—",
    },
    {
      headerName: "Chunks",
      field: "chunks",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params) => formatNumber(params.value),
    },
    {
      headerName: "Avg Chunk Size",
      field: "avg_chunk_size",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params) => formatAverageChunkSize(params.value),
    },
    {
      headerName: "Status",
      field: "status",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueGetter: (params) => params.data.status || "—",
    },
  ];
};
