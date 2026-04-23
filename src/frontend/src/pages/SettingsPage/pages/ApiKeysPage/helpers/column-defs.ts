import type { ColDef } from "ag-grid-community";
import TableAutoCellRender from "@/components/core/parameterRenderComponent/components/tableComponent/components/tableAutoCellRender";
import { IpRestrictionCell } from "../components/IpRestrictionCell";
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
      cellRenderer: IpRestrictionCell,
      cellClass: "group",
      flex: 2,
      resizable: true,
    });
  }

  return columns;
};
