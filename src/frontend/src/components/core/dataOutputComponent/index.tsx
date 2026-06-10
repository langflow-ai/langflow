import type { ColDef, ColGroupDef } from "ag-grid-community";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { useUtilityStore } from "@/stores/utilityStore";
import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { extractColumnsFromRows } from "../../../utils/utils";

type DataOutputRow = Record<string, unknown>;

function DataOutputComponent({
  pagination,
  rows,
  columnMode = "union",
}: {
  pagination: boolean;
  rows: unknown[];
  columnMode?: "intersection" | "union";
}) {
  const maxItemsLength = useUtilityStore(
    (state) => state.serializationMaxItemsLength,
  );
  const { t } = useTranslation();
  const [rowsInternal, setRowsInternal] = useState<DataOutputRow[]>(
    rows
      .slice(0, maxItemsLength)
      .map((row) =>
        row !== null && typeof row === "object"
          ? (row as DataOutputRow)
          : { data: row },
      ),
  );

  useEffect(() => {
    const rowsSliced = rows.slice(0, maxItemsLength);
    setRowsInternal(
      rowsSliced.map((row) =>
        row !== null && typeof row === "object"
          ? (row as DataOutputRow)
          : { data: row },
      ),
    );
  }, [rows, maxItemsLength]);

  const columns = extractColumnsFromRows(rowsInternal, columnMode);

  const columnDefs = columns.map((col, idx) => ({
    ...col,
    resizable: true,
  })) as (ColDef<DataOutputRow> | ColGroupDef<DataOutputRow>)[];

  return (
    <TableComponent
      autoSizeStrategy={{
        type: "fitGridWidth",
        defaultMinWidth: maxItemsLength,
      }}
      key={"dataOutputComponent"}
      overlayNoRowsTemplate={t("settings.noDataAvailable")}
      paginationInfo={
        rows.length > maxItemsLength ? rows[maxItemsLength] : undefined
      }
      suppressRowClickSelection={true}
      pagination={pagination}
      columnDefs={columnDefs}
      rowData={rowsInternal}
    />
  );
}

export default DataOutputComponent;
