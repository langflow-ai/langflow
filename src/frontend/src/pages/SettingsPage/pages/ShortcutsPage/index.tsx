import { ColDef, ColGroupDef } from "ag-grid-community";
import { useState } from "react";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import TableComponent from "../../../../components/tableComponent";

export default function ShortcutsPage() {
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
    { headerName: "Functionality", field: "name", flex: 1, editable: false }, //This column will be twice as wide as the others
    {
      field: "shortcut",
      flex: 2,
      editable: false,
    },
  ]);

  const [rowData, setRowData] = useState([
    {
      name: "Open node advanced settings",
      shortcut: advancedShortcut,
    },
    {
      name: "Minimize",
      shortcut: minizmizeShortcut,
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
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Shortcuts
            <ForwardedIconComponent
              name="Keyboard"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Customize, manage and create shortcuts for quick access to
            frequently used actions.
          </p>
        </div>
      </div>

      <div className="flex h-full w-full flex-col justify-between">
        <TableComponent columnDefs={colDefs} rowData={rowData} />
      </div>
    </div>
  );
}
