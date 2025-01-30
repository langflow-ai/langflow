import TableAdvancedToggleCellRender from "@/components/core/parameterRenderComponent/components/tableComponent/components/tableAdvancedToggleCellRender";
import TableNodeCellRender from "@/components/core/parameterRenderComponent/components/tableComponent/components/tableNodeCellRender";
import { ColDef, ValueGetterParams } from "ag-grid-community";
import { useMemo } from "react";

const useColumnDefs = (
  nodeId: string,
  open: boolean,
  isTweaks?: boolean,
  hideVisibility?: boolean,
) => {
  const columnDefs: ColDef[] = useMemo(() => {
    const colDefs: ColDef[] = [
      {
        headerName: "Field Name",
        field: "display_name",
        valueGetter: (params) => {
          const templateParam = params.data;
          return (
            (templateParam.display_name
              ? templateParam.display_name
              : templateParam.name) ?? params.data.key
          );
        },
        wrapText: true,
        autoHeight: true,
        flex: 1,
        resizable: false,
        cellClass: "no-border",
      },
      {
        headerName: "Description",
        field: "info",
        tooltipField: "info",
        wrapText: true,
        autoHeight: true,
        flex: 2,
        resizable: false,
        cellClass: "no-border",
      },
      {
        headerName: "Value",
        field: "value",
        cellRenderer: TableNodeCellRender,
        valueGetter: (params: ValueGetterParams) => {
          return {
            nodeId: nodeId,
            parameterId: params.data.key,
            isTweaks,
          };
        },
        suppressKeyboardEvent: (params) =>
          params.event.key === "a" &&
          (params.event.ctrlKey || params.event.metaKey),
        minWidth: 340,
        autoHeight: true,
        flex: 1,
        resizable: false,
        cellClass: "no-border",
      },
    ];
    if (!hideVisibility) {
      colDefs.push({
        headerName: "Show",
        field: "advanced",
        cellRenderer: TableAdvancedToggleCellRender,
        valueGetter: (params: ValueGetterParams) => {
          return {
            nodeId,
            parameterId: params.data.key,
          };
        },
        editable: false,
        maxWidth: 80,
        resizable: false,
        cellClass: "no-border",
      });
    }
    return colDefs;
  }, [open]);

  return columnDefs;
};

export default useColumnDefs;
