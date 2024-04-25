import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-quartz.css"; // Optional Theme applied to the grid
import { AgGridReact } from "ag-grid-react";
import { useState } from "react";
import { Card, CardContent, CardFooter } from "../ui/card";

export default function TableComponent() {
  // Column Definitions: Defines the columns to be displayed.
  const [colDefs, setColDefs] = useState([
    { headerName: "Variable Name", field: "name", flex: 1, editable: true }, //This column will be twice as wide as the others
    {
      field: "type",
      cellEditor: "agSelectCellEditor",
      cellEditorParams: {
        values: ["Prompt", "Credential"],
        valueListGap: 10,
      },
      flex: 1,
      editable: true,
    },
    {
      field: "value",
      cellEditor: "agLargeTextCellEditor",
      cellEditorPopup: true,
      flex: 2,
      editable: true,
    },
    {
      headerName: "Default Fields",
      field: "defaultFields",
      flex: 1,
      editable: true,
    },
  ]);

  const [rowData, setRowData] = useState([
    {
      name: "OpenAI Key",
      type: "Credential",
      value: "apijpioj09u302j0982ejf",
      defaultFields: "Open AI API Key",
    },
    {
      name: "Prompt",
      type: "Prompt",
      value: `Answer user's questions based on the document below:

    ---
    
    {Document}
    
    ---
    
    Question:
    {Question}
    
    Answer:
    `,
      defaultFields: ["Prompt"],
    },
    {
      name: "Azure Key",
      type: "Credential",
      value: "awowkdenvoaimojndofunoweoij0293u0n2e08n23",
      defaultFields: ["Azure API Key"],
    },
  ]);

  return (
    <Card className="mb-12 h-full">
      <CardContent className="flex h-full flex-col pt-4">
        <div
          className="ag-theme-quartz h-full" // applying the grid theme
        >
          <AgGridReact columnDefs={colDefs} rowData={rowData} />
        </div>
      </CardContent>
      <CardFooter>
        <div className="text-xs text-muted-foreground">
          Showing <strong>1-3</strong> of <strong>3</strong> products
        </div>
      </CardFooter>
    </Card>
  );
}
