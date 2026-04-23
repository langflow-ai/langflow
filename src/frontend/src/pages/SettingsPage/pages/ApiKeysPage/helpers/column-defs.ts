import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import type { IApiKeysDataArray } from "@/controllers/API/queries/api-keys";
import { isTimeStampString } from "@/utils/utils";
import { PlainTableCell } from "../components/PlainTableCell";

/** Matches DateReader formatting; avoids TableAutoCellRender / StringReader → TextModal on cell click. */
function formatApiKeyDateTime(value: unknown): string {
  if (value == null || value === "") {
    return "";
  }
  const s = String(value);
  if (s === "Never") {
    return "Never";
  }
  if (isTimeStampString(s)) {
    const date = new Date(s);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    const seconds = String(date.getSeconds()).padStart(2, "0");
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  }
  return s;
}

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
      cellRenderer: PlainTableCell,
      valueFormatter: (p: ValueFormatterParams<IApiKeysDataArray>) =>
        formatApiKeyDateTime(p.value),
      flex: 1,
    },
    {
      headerName: "Last Used",
      field: "last_used_at",
      cellRenderer: PlainTableCell,
      valueFormatter: (p: ValueFormatterParams<IApiKeysDataArray>) =>
        formatApiKeyDateTime(p.value),
      flex: 1,
    },
    {
      headerName: "Total Uses",
      field: "total_uses",
      cellRenderer: PlainTableCell,
      valueFormatter: (p: ValueFormatterParams<IApiKeysDataArray>) =>
        p.value != null ? String(p.value) : "",
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
