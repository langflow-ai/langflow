import { ColDef, ValueGetterParams } from "ag-grid-community";
import { useMemo } from "react";
import TableNodeCellRender from "../../../components/tableComponent/components/tableNodeCellRender";
import TableToggleCellRender from "../../../components/tableComponent/components/tableToggleCellRender";
import { APIClassType } from "../../../types/api";

const useColumnDefs = (
  nodeClass: APIClassType,
  handleNodeClass: (
    newNodeClass: APIClassType,
    name: string,
    code: string,
    type?: string,
  ) => void,
  nodeId: string,
  changeAdvanced: (n: string) => void,
  open: boolean,
) => {
  const columnDefs: ColDef[] = useMemo(
    () => [
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
            value: params.data.value,
            nodeId: nodeId,
            nodeClass: nodeClass,
            handleNodeClass: handleNodeClass,
          };
        },
        minWidth: 340,
        autoHeight: true,
        flex: 1,
        resizable: false,
        cellClass: "no-border",
      },
      {
        headerName: "Show",
        field: "advanced",
        cellRenderer: TableToggleCellRender,
        valueGetter: (params: ValueGetterParams) => {
          return {
            name: params.data.name,
            enabled: !params.data.advanced,
            setEnabled: () => {
              changeAdvanced(params.data.key);
            },
          };
        },
        editable: false,
        maxWidth: 80,
        resizable: false,
        cellClass: "no-border",
      },
    ],
    [open, nodeClass],
  );

  return columnDefs;
};

export default useColumnDefs;
