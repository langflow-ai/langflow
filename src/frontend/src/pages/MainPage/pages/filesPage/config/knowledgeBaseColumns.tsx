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
      headerName: "Name",
      field: "name",
      flex: 2,
      sortable: false,
      headerCheckboxSelection: true,
      checkboxSelection: true,
      editable: false,
      filter: "agTextColumnFilter",
      cellClass: baseCellClass,
      cellRenderer: (params) => (
        <div className="flex items-center gap-3 font-medium">
          <div className="flex flex-col">
            <div className="text-sm font-medium">{params.value}</div>
          </div>
        </div>
      ),
    },
    {
      headerName: "Embedding Model",
      field: "embedding_provider",
      flex: 2,
      sortable: false,
      filter: "agTextColumnFilter",
      editable: false,
      cellClass: baseCellClass,
      tooltipValueGetter: (params) => params.data.embedding_model || "Unknown",
      valueGetter: (params) => params.data.embedding_model || "Unknown",
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
      headerName: "Words",
      field: "words",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params) => formatNumber(params.value),
    },
    {
      headerName: "Characters",
      field: "characters",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params) => formatNumber(params.value),
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
      headerName: "Avg Chunks",
      field: "avg_chunk_size",
      flex: 1,
      sortable: false,
      editable: false,
      cellClass: baseCellClass,
      valueFormatter: (params) => formatAverageChunkSize(params.value),
    },
  ];
};
