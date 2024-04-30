import { ColDef, ColGroupDef } from "ag-grid-community";
import { useState } from "react";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import TableComponent from "../../../../components/tableComponent";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../../components/ui/card";

export default function ShortcutsPage() {
  const advancedShortcut = "Ctrl + Shift + A";
  const minizmizeShortcut = "Ctrl + Shift + Q";
  const codeShortcut = "Ctrl + Shift + C";
  const copyShortcut = "Ctrl + C";
  const duplicateShortcut = "Ctrl + D";
  const shareShortcut = "Ctrl + Shift + S";
  const docsShortcut = "Ctrl + Shift + D";
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

  const [nodesRowData, setNodesRowData] = useState([
    {
      name: "Component Advanced Settings",
      shortcut: advancedShortcut,
    },
    {
      name: "Component Minimize",
      shortcut: minizmizeShortcut,
    },
    {
      name: "Component Code",
      shortcut: codeShortcut,
    },
    {
      name: "Component Copy",
      shortcut: copyShortcut,
    },
    {
      name: "Component Duplicate",
      shortcut: duplicateShortcut,
    },
    {
      name: "Component Share",
      shortcut: shareShortcut,
    },
    {
      name: "Component Docs",
      shortcut: docsShortcut,
    },
    {
      name: "Component Save",
      shortcut: saveShortcut,
    },
    {
      name: "Component Delete",
      shortcut: deleteShortcut,
    },
    {
      name: "Open Playground",
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
    <div className="flex h-full w-full flex-col gap-6">
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
            Manage Shortcuts for quick access to
            frequently used actions.
          </p>
        </div>
      </div>
      <div className="grid gap-6 pb-8">
        <Card x-chunk="dashboard-04-chunk-2" className="pt-4">
          <CardContent>
            <TableComponent
              domLayout="autoHeight"
              pagination={false}
              columnDefs={colDefs}
              rowData={nodesRowData}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
