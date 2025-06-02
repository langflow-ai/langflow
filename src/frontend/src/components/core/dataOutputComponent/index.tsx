import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { MAX_ITEMS_LENGTH } from "@/constants/constants";
import { ColDef, ColGroupDef } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { useEffect, useState } from "react";
import { extractColumnsFromRows } from "../../../utils/utils";

function DataOutputComponent({
  pagination,
  rows,
  columnMode = "union",
}: {
  pagination: boolean;
  rows: any[];
  columnMode?: "intersection" | "union";
}) {
  const [rowsInternal, setRowsInternal] = useState(
    rows.slice(0, MAX_ITEMS_LENGTH),
  );

  useEffect(() => {
    const rowsSliced = rows.slice(0, MAX_ITEMS_LENGTH);
    if (rowsSliced.some((row) => typeof row !== "object")) {
      setRowsInternal(rowsSliced.map((row) => ({ data: row })));
    } else {
      setRowsInternal(rowsSliced);
    }
  }, [rows]);

  const columns = extractColumnsFromRows(rowsInternal, columnMode);

  const columnDefs = columns.map((col, idx) => ({
    ...col,
    resizable: true,
  })) as (ColDef<any> | ColGroupDef<any>)[];

  return (
    <TableComponent
      autoSizeStrategy={{
        type: "fitGridWidth",
        defaultMinWidth: MAX_ITEMS_LENGTH,
      }}
      key={"dataOutputComponent"}
      overlayNoRowsTemplate="No data available"
      paginationInfo={
        rows.length > MAX_ITEMS_LENGTH ? rows[MAX_ITEMS_LENGTH] : undefined
      }
      suppressRowClickSelection={true}
      pagination={pagination}
      columnDefs={columnDefs}
      rowData={rowsInternal}
    />
  );
}

export default DataOutputComponent;
