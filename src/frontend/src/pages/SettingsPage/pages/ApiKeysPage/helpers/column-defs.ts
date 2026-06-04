import TableAutoCellRender from "@/components/core/parameterRenderComponent/components/tableComponent/components/tableAutoCellRender";
import CreatedAtCellRender from "../components/CreatedAtCellRender";
import ExpiryDateCellRender from "../components/ExpiryDateCellRender";
import LastUsedAtCellRender from "../components/LastUsedAtCellRender";

export const getColumnDefs = (t: (key: string) => string) => {
  return [
    {
      headerCheckboxSelection: true,
      checkboxSelection: true,
      showDisabledCheckboxes: true,
      headerName: t("settings.apiKeys.columnName"),
      field: "name",
      cellRenderer: TableAutoCellRender,
      flex: 2,
    },
    {
      headerName: t("settings.apiKeys.columnKey"),
      field: "api_key",
      cellRenderer: TableAutoCellRender,
      flex: 1,
    },
    {
      headerName: t("settings.apiKeys.columnCreated"),
      field: "created_at",
      cellRenderer: CreatedAtCellRender,
      flex: 1,
    },
    {
      headerName: t("settings.apiKeys.columnLastUsed"),
      field: "last_used_at",
      cellRenderer: LastUsedAtCellRender,
      flex: 1,
    },
    {
      headerName: t("settings.apiKeys.columnExpires"),
      field: "expires_at",
      cellRenderer: ExpiryDateCellRender,
      flex: 1,
    },
    {
      headerName: t("settings.apiKeys.columnTotalUses"),
      field: "total_uses",
      cellRenderer: TableAutoCellRender,
      flex: 1,
      resizable: false,
    },
  ];
};
