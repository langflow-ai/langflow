import TableAutoCellRender from "../../../../../components/tableComponent/components/tableAutoCellRender";
import { useTranslation } from "react-i18next";

export const getColumnDefs = () => {
  const { t } = useTranslation();
  return [
    {
      headerCheckboxSelection: true,
      checkboxSelection: true,
      showDisabledCheckboxes: true,
      headerName: t("Name"),
      field: "name",
      cellRenderer: TableAutoCellRender,
      flex: 2,
    },
    {
      headerName: t("Key"),
      field: "api_key",
      cellRenderer: TableAutoCellRender,
      flex: 1,
    },
    {
      headerName: t("Created"),
      field: "created_at",
      cellRenderer: TableAutoCellRender,
      flex: 1,
    },
    {
      headerName: t("Last Used"),
      field: "last_used_at",
      cellRenderer: TableAutoCellRender,
      flex: 1,
    },
    {
      headerName: t("Total Uses"),
      field: "total_uses",
      cellRenderer: TableAutoCellRender,
      flex: 1,
      resizable: false,
    },
  ];
};
