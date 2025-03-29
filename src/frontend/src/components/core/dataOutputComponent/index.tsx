import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
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
  const [rowsInternal, setRowsInternal] = useState(rows.slice(0, 1000));

  useEffect(() => {
    const rowsSliced = rows.slice(0, 1000);
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
      autoSizeStrategy={{ type: "fitGridWidth", defaultMinWidth: 100 }}
      key={"dataOutputComponent"}
      overlayNoRowsTemplate="No data available"
      paginationInfo={rows.length > 1000 ? rows[1000] : undefined}
      suppressRowClickSelection={true}
      pagination={pagination}
      columnDefs={columnDefs}
      rowData={rowsInternal}
    />
  );
}

export default DataOutputComponent;
