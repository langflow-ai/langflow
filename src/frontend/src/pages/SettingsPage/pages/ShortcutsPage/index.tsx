import { ColDef, ColGroupDef } from "ag-grid-community";
import { useState } from "react";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import TableComponent from "../../../../components/tableComponent";
import { Card, CardContent } from "../../../../components/ui/card";

export default function ShortcutsPage() {
  const isMac = navigator.userAgent.toUpperCase().includes("MAC");
  const advancedShortcut = `${isMac ? "Cmd" : "Ctrl"} + Shift + A`;
  const minizmizeShortcut = `${isMac ? "Cmd" : "Ctrl"} + Shift + Q`;
  const codeShortcut = `${isMac ? "Cmd" : "Ctrl"} + Shift + C`;
  const copyShortcut = `${isMac ? "Cmd" : "Ctrl"} + C`;
  const duplicateShortcut = `${isMac ? "Cmd" : "Ctrl"} + D`;
  const shareShortcut = `${isMac ? "Cmd" : "Ctrl"} + Shift + S`;
  const docsShortcut = `${isMac ? "Cmd" : "Ctrl"} + Shift + D`;
  const saveShortcut = `${isMac ? "Cmd" : "Ctrl"} + S`;
  const deleteShortcut = `Backspace`;
  const interactionShortcut = `${isMac ? "Cmd" : "Ctrl"} + K`;
  const undoShortcut = `${isMac ? "Cmd" : "Ctrl"} + Z`;
  const redoShortcut = `${isMac ? "Cmd" : "Ctrl"} + Y`;

  // Column Definitions: Defines the columns to be displayed.
  const [colDefs, setColDefs] = useState<(ColDef<any> | ColGroupDef<any>)[]>([
    {
      headerName: "Functionality",
      field: "name",
      flex: 1,
      editable: false,
    }, //This column will be twice as wide as the others
    {
      field: "shortcut",
      flex: 2,
      editable: false,
      resizable: false,
    },
  ]);

  const [nodesRowData, setNodesRowData] = useState([
    {
      name: "Advanced Settings Component",
      shortcut: advancedShortcut,
      resizable: false,
    },
    {
      name: "Minimize Component",
      shortcut: minizmizeShortcut,
      resizable: false,
    },
    {
      name: "Code Component",
      shortcut: codeShortcut,
      resizable: false,
    },
    {
      name: "Copy Component",
      shortcut: copyShortcut,
      resizable: false,
    },
    {
      name: "Duplicate Component",
      shortcut: duplicateShortcut,
      resizable: false,
    },
    {
      name: "Share Component",
      shortcut: shareShortcut,
      resizable: false,
    },
    {
      name: "Docs Component",
      shortcut: docsShortcut,
      resizable: false,
    },
    {
      name: "Save Component",
      shortcut: saveShortcut,
      resizable: false,
    },
    {
      name: "Delete Component",
      shortcut: deleteShortcut,
      resizable: false,
    },
    {
      name: "Open Playground",
      shortcut: interactionShortcut,
      resizable: false,
    },
    {
      name: "Undo",
      shortcut: undoShortcut,
      resizable: false,
    },
    {
      name: "Redo",
      shortcut: redoShortcut,
      resizable: false,
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
            Manage Shortcuts for quick access to frequently used actions.
          </p>
        </div>
      </div>
      <div className="grid gap-6 pb-8">
        <Card x-chunk="dashboard-04-chunk-2" className="h-full pt-4">
          <CardContent className="h-full">
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
