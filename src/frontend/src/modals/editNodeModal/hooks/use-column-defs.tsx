import { ColDef, ValueGetterParams } from "ag-grid-community";
import { useMemo } from "react";
import TableAutoCellRender from "../../../components/tableComponent/components/tableAutoCellRender";
import TableNodeCellRender from "../../../components/tableComponent/components/tableNodeCellRender";
import TableToggleCellRender from "../../../components/tableComponent/components/tableToggleCellRender";
import TableTooltipRender from "../../../components/tableComponent/components/tableTooltipRender";
import TableMultilineCellRender from "../../../components/tableComponent/components/tableMultilineCellRender";

const useColumnDefs = (
  myData: any,
  handleOnNewValue: (newValue: any, name: string) => void,
  changeAdvanced: (n: string) => void,
  open: boolean,
) => {
  const columnDefs: ColDef[] = useMemo(
    () => [
      {
        headerName: "Name",
        field: "display_name",
        valueGetter: (params) => {
          const templateParam = params.data;
          return (
            (templateParam.display_name
              ? templateParam.display_name
              : templateParam.name) ?? params.data.key
          );
        },
        tooltipField: "display_name",
        tooltipComponent: TableTooltipRender,
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
        tooltipComponent: TableTooltipRender,
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
            nodeClass: myData.current.node,
            handleOnNewValue: handleOnNewValue,
            handleOnChangeDb: (value, key) => {
              myData.current.node!.template[key].load_from_db = value;
            },
          };
        },
        minWidth: 330,
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
    [open],
  );

  return columnDefs;
};

export default useColumnDefs;
