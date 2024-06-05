import { ColDef, ColGroupDef } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { FlowPoolObjectType } from "../../types/chat";
import { extractColumnsFromRows } from "../../utils/utils";
import TableComponent from "../tableComponent";

function RecordsOutputComponent({
  flowPool,
  pagination,
}: {
  flowPool: FlowPoolObjectType;
  pagination: boolean;
}) {
  const rows = flowPool?.data?.artifacts?.records ?? [];
  const columns = extractColumnsFromRows(rows, "union");
  const columnDefs = columns.map((col, idx) => ({
    ...col,
    resizable: idx !== columns.length - 1,
    flex: idx !== columns.length - 1 ? 1 : 2,
  })) as (ColDef<any> | ColGroupDef<any>)[];

  return (
    <TableComponent
      overlayNoRowsTemplate="No data available"
      suppressRowClickSelection={true}
      pagination={pagination}
      columnDefs={columnDefs}
      rowData={rows}
    />
  );
}

export default RecordsOutputComponent;
