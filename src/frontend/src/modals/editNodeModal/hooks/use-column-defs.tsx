import { ColDef, ValueGetterParams } from "ag-grid-community";
import { useMemo } from "react";
import TableNodeCellRender from "../../../components/tableComponent/components/tableNodeCellRender";
import TableToggleCellRender from "../../../components/tableComponent/components/tableToggleCellRender";
import { NodeDataType } from "../../../types/flow";
import { useTranslation } from "react-i18next";

const useColumnDefs = (
  myData: NodeDataType,
  handleOnNewValue: (newValue: any, name: string, setDb?: boolean) => void,
  changeAdvanced: (n: string) => void,
  open: boolean,
) => {
  const { t } = useTranslation();
  const columnDefs: ColDef[] = useMemo(
    () => [
      {
        headerName: t("Field Name"),
        field: "display_name",
        valueGetter: (params) => {
          const templateParam = params.data;
          return (
            (templateParam.display_name
              ? t(templateParam.display_name)
              : t(templateParam.name)) ?? params.data.key
          );
        },
        wrapText: true,
        autoHeight: true,
        flex: 1,
        resizable: false,
        cellClass: "no-border",
      },
      {
        headerName: t("Description"),
        field: "info",
        valueGetter: (params) => {
          const templateParam = params.data;
          return templateParam.info ? t(templateParam.info) : "";
        },
        tooltipValueGetter: (params) => {
          const templateParam = params.data;
          return templateParam.info ? t(templateParam.info) : "";
        },
        wrapText: true,
        autoHeight: true,
        flex: 2,
        resizable: false,
        cellClass: "no-border",
      },
      {
        headerName: t("Value"),
        field: "value",
        cellRenderer: TableNodeCellRender,
        valueGetter: (params: ValueGetterParams) => {
          return {
            value: params.data.value,
            nodeClass: myData.node,
            handleOnNewValue: handleOnNewValue,
          };
        },
        minWidth: 340,
        autoHeight: true,
        flex: 1,
        resizable: false,
        cellClass: "no-border",
      },
      {
        headerName: t("Show"),
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
    [open, myData],
  );

  return columnDefs;
};

export default useColumnDefs;
