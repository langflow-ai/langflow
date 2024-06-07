import { ColDef, ColGroupDef } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { extractColumnsFromRows } from "../../utils/utils";
import TableComponent from "../tableComponent";

function RecordsOutputComponent({
  pagination,
  rows,
  columnMode = "union",
}: {
  pagination: boolean;
  rows: any;
  columnMode?: "intersection" | "union";
}) {
  console.log("rows", rows);
  const columns = extractColumnsFromRows(rows, columnMode);
  console.log("columns", columns);

  const columnDefs = columns.map((col, idx) => ({
    ...col,
    resizable: idx !== columns.length - 1,
    flex: idx !== columns.length - 1 ? 1 : 2,
  })) as (ColDef<any> | ColGroupDef<any>)[];

  return (
    <TableComponent
      key={"recordsOutputComponent"}
      overlayNoRowsTemplate="No data available"
      suppressRowClickSelection={true}
      pagination={pagination}
      columnDefs={columnDefs}
      rowData={rows}
    />
  );
}

export default RecordsOutputComponent;
