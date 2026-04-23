import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import TableAutoCellRender from "@/components/core/parameterRenderComponent/components/tableComponent/components/tableAutoCellRender";
import type { IApiKeysDataArray } from "@/controllers/API/queries/api-keys";
import { PlainTableCell } from "../components/PlainTableCell";

export const getColumnDefs = (options?: { hideIpRestriction?: boolean }) => {
  const columns: ColDef[] = [
    {
      headerCheckboxSelection: true,
      checkboxSelection: true,
      showDisabledCheckboxes: true,
      headerName: "Name",
      field: "name",
      cellRenderer: PlainTableCell,
      valueFormatter: (p: ValueFormatterParams<IApiKeysDataArray>) =>
        p.value != null && p.value !== "" ? String(p.value) : "Untitled",
      flex: 2,
    },
    {
      headerName: "Key",
      field: "api_key",
      cellRenderer: PlainTableCell,
      flex: 1,
    },
    {
      headerName: "Created",
      field: "created_at",
      cellRenderer: TableAutoCellRender,
      flex: 1,
    },
    {
      headerName: "Last Used",
      field: "last_used_at",
      cellRenderer: TableAutoCellRender,
      flex: 1,
    },
    {
      headerName: "Total Uses",
      field: "total_uses",
      cellRenderer: TableAutoCellRender,
      flex: 1,
      resizable: false,
    },
  ];

  if (!options?.hideIpRestriction) {
    columns.push({
      headerName: "IP Restriction",
      field: "allowed_ips",
      cellRenderer: PlainTableCell,
      valueFormatter: (p: ValueFormatterParams<IApiKeysDataArray>) =>
        p.value ? String(p.value) : "—",
      flex: 2,
      resizable: true,
    });
  }

  return columns;
};
