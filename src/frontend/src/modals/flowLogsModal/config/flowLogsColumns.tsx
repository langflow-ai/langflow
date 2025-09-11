import DictAreaModal from "@/modals/dictAreaModal";
import { convertUTCToLocalTimezone } from "@/utils/utils";
import type { ColDef } from "ag-grid-community";

export const createFlowLogsColumns = (): ColDef[] => {
  const baseCellClass =
    "text-muted-foreground select-text cursor-default";
  
  const modalCellClass =
    "text-muted-foreground cursor-pointer";

  return [
    {
      headerName: "ID",
      field: "id",
      minWidth: 320,
      flex: 1,
      filter: false,
      sortable: false,
      editable: false,
      cellClass: `${baseCellClass} cursor-default`,
      cellRenderer: (params) => (
        <div className="flex items-center">
          <div className="truncate" title={params.value}>
            {params.value}
          </div>
        </div>
      ),
    },
    {
      headerName: "Timestamp",
      field: "timestamp",
      minWidth: 200,
      flex: 0.8,
      sort: "desc",
      editable: false,
      cellClass: `${baseCellClass} cursor-default`,
      valueFormatter: (params) => {
        if (!params.value) return "";
        return convertUTCToLocalTimezone(params.value);
      },
    },
    {
      headerName: "Vertex ID",
      field: "vertex_id",
      flex: 1,
      filter: false,
      sortable: false,
      editable: false,
      cellClass: `${baseCellClass} cursor-default`,
      cellRenderer: (params) => (
        <div className="flex items-center">
          <div className="truncate" title={params.value}>
            {params.value}
          </div>
        </div>
      ),
    },
    {
      headerName: "Target ID",
      field: "target_id", 
      flex: 1,
      filter: false,
      sortable: false,
      editable: false,
      cellClass: `${baseCellClass} cursor-default`,
      cellRenderer: (params) => (
        <div className="flex items-center ">
          <div className="truncate" title={params.value}>
            {params.value || "-"}
          </div>
        </div>
      ),
    },

    {
      headerName: "Inputs",
      field: "inputs",
      flex: 1.5,
      editable: false,
      filter: true,
      cellClass: modalCellClass,
      cellRenderer: (params) => {
        const inputs = params.value;

        if (!inputs || typeof inputs !== 'object') {
          return <div className="text-muted-foreground">-</div>;
        }
                
        return (
          <DictAreaModal value={inputs}>
            <div className="flex items-center">
              <span className="truncate">{JSON.stringify(inputs)}</span>
            </div>
          </DictAreaModal>
        );
      },
    },
    {
      headerName: "Outputs",
      field: "outputs",
      flex: 1.5,
      editable: false,
      filter: true,
      cellClass: modalCellClass,
      cellRenderer: (params) => {
        const outputs = params.value;

        if (!outputs || typeof outputs !== 'object') {
          return <div className="text-muted-foreground">-</div>;
        }
                
        return (
          <DictAreaModal value={outputs}>
             <div className="flex items-center">
              <span className="truncate">{JSON.stringify(outputs)}</span>
            </div>
          </DictAreaModal>
        );
      },
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
      cellRenderer: (params) => {
        const status = params.value;
 
        return (
          <div className="flex items-center">
            <span className="inline-flex items-center px-2 py-1 font-medium truncate">
              {status}
            </span>
          </div>
        );
      },
    },
  ];
};