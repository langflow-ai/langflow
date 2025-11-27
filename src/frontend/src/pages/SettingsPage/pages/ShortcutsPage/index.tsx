import type { ColDef } from "ag-grid-community";
import { useEffect, useState } from "react";
import { toCamelCase } from "@/utils/utils";
import ForwardedIconComponent from "../../../../components/common/genericIconComponent";
import TableComponent from "../../../../components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "../../../../components/ui/button";
import { defaultShortcuts } from "../../../../constants/constants";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import CellRenderShortcuts from "./CellRenderWrapper";
import EditShortcutButton from "./EditShortcutButton";

export default function ShortcutsPage() {
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const setShortcuts = useShortcutsStore((state) => state.setShortcuts);

  // Column Definitions: Defines the columns to be displayed.
  const colDefs: ColDef[] = [
    {
      headerName: "Functionality",
      field: "display_name",
      flex: 1,
      editable: false,
      resizable: false,
    }, //This column will be twice as wide as the others
    {
      headerName: "Keyboard Shortcut",
      field: "shortcut",
      flex: 2,
      editable: false,
      resizable: false,
      cellRenderer: CellRenderShortcuts,
    },
  ];

  const [nodesRowData, setNodesRowData] = useState<
    Array<{ name: string; shortcut: string }>
  >([]);

  useEffect(() => {
    setNodesRowData(shortcuts);
  }, [shortcuts]);

  const [open, setOpen] = useState(false);
  const updateUniqueShortcut = useShortcutsStore(
    (state) => state.updateUniqueShortcut
  );

  function handleRestore() {
    setShortcuts(defaultShortcuts);
    defaultShortcuts.forEach(({ name, shortcut }) => {
      const fixedName = toCamelCase(name);
      updateUniqueShortcut(fixedName, shortcut);
    });
    localStorage.removeItem("langflow-shortcuts");
  }

  return (
    <div className="flex h-full w-full flex-col gap-4">
      <div className="flex w-full items-center justify-between gap-4">
        <div className="flex flex-col w-full">
          <h2 className="text-primary-font flex gap-2 items-center text-lg font-medium">
            Shortcuts
            <ForwardedIconComponent
              name="Keyboard"
              className="h-4 w-4 text-menu"
            />
          </h2>
          <p className="text-sm text-secondary-font">
            Manage Shortcuts for quick access to frequently used actions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {open && (
            <EditShortcutButton
              disable={selectedRows.length === 0}
              shortcut={selectedRows}
              defaultShortcuts={shortcuts}
              open={open}
              setOpen={setOpen}
              setSelected={setSelectedRows}
            >
              <div style={{ display: "none" }} />
            </EditShortcutButton>
          )}
          <Button
            variant="default"
            className="flex gap-2"
            onClick={handleRestore}
          >
            <ForwardedIconComponent name="RotateCcw" className="w-4" />
            Restore
          </Button>
        </div>
      </div>
      <div className="flex h-full flex-col gap-2 bg-background-surface border border-primary-border rounded-lg p-4">
        {colDefs && nodesRowData.length > 0 && (
          <TableComponent
            suppressRowClickSelection={true}
            domLayout="autoHeight"
            pagination={false}
            columnDefs={colDefs}
            rowData={nodesRowData}
            onCellDoubleClicked={(e) => {
              setSelectedRows([e.data.name]);
              setOpen(true);
            }}
          />
        )}
      </div>
    </div>
  );
}
