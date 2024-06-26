import { ColDef, ColGroupDef } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-balham.css"; // Optional Theme applied to the grid
import { extractColumnsFromRows } from "../../utils/utils";
import TableComponent from "../tableComponent";
import { useTranslation } from "react-i18next";

function DataOutputComponent({
  pagination,
  rows,
  columnMode = "union",
}: {
  pagination: boolean;
  rows: any;
  columnMode?: "intersection" | "union";
}) {
  const { t } = useTranslation();
  const columns = extractColumnsFromRows(rows, columnMode);

  const columnDefs = columns.map((col, idx) => ({
    ...col,
    resizable: true,
  })) as (ColDef<any> | ColGroupDef<any>)[];

  return (
    <TableComponent
      autoSizeStrategy={{ type: "fitGridWidth", defaultMinWidth: 100 }}
      key={"dataOutputComponent"}
      overlayNoRowsTemplate={t("No data available")}
      suppressRowClickSelection={true}
      pagination={pagination}
      columnDefs={columnDefs}
      rowData={rows}
    />
  );
}

export default DataOutputComponent;
