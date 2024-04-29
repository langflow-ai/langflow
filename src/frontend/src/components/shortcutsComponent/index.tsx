import "ag-grid-community/styles/ag-grid.css"; // Mandatory CSS required by the grid
import "ag-grid-community/styles/ag-theme-quartz.css"; // Optional Theme applied to the grid
import { AgGridReact } from "ag-grid-react";
import { ColDef,ColGroupDef } from 'ag-grid-community';
import { useState } from "react";
import { Card, CardContent, CardFooter } from "../ui/card";

export default function ShortcutsComponent() {
  const advancedShortcut = "Ctrl + shift + A";
  const minizmizeShortcut = "Ctrl + shift + Q";
  const codeShortcut = "Ctrl + shift + C";
  const copyShortcut = "Ctrl + C";
  const duplicateShortcut = "Ctrl + D";
  const shareShortcut = "Ctrl + shift + S";
  const docsShortcut = "Ctrl + shift + D";
  const saveShortcut = "Ctrl + S";
  const deleteShortcut = "Backspace";
  const interactionShortcut = "Ctrl + K";
  const undoShortcut = "Ctrl + Z";
  const redoShortcut = "Ctrl + Y";


  // Column Definitions: Defines the columns to be displayed.
  const [colDefs, setColDefs] = useState<(ColDef<any> | ColGroupDef<any>)[]>([
    { headerName: "Functionality",
     field: "name",
      flex: 1,
       editable: false 
      }, //This column will be twice as wide as the others
    {
      field: "shortcut",
      flex: 2,
      editable: false,
    }
  ]);

  const [rowData, setRowData] = useState([
    {
      name: "Open node advanced settings",
      shortcut: advancedShortcut,
    },
    {
      name: "Minimize",
      shortcut: minizmizeShortcut
    },
    {
      name: "Open Code modal",
      shortcut: codeShortcut,
    },
    {
      name: "Copy",
      shortcut: copyShortcut,
    },
    {
      name: "Duplicate",
      shortcut: duplicateShortcut,
    },
    {
      name: "Share",
      shortcut: shareShortcut,
    },
    {
      name: "Open docs",
      shortcut: docsShortcut,
    },
    {
      name: "Save",
      shortcut: saveShortcut,
    },
    {
      name: "Delete",
      shortcut: deleteShortcut,
    },
    {
      name: "Open interaction panel",
      shortcut: interactionShortcut,
    },
    {
      name: "Undo",
      shortcut: undoShortcut,
    },
    {
      name: "Redo",
      shortcut: redoShortcut,
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
