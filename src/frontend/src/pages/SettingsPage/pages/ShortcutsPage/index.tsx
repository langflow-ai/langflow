import { toCamelCase } from "@/utils/utils";
import { ColDef } from "ag-grid-community";
import { useEffect, useState } from "react";
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
    (state) => state.updateUniqueShortcut,
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
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Shortcuts
            <ForwardedIconComponent
              name="Keyboard"
              className="text-primary ml-2 h-5 w-5"
            />
          </h2>
          <p className="text-muted-foreground text-sm">
            Manage Shortcuts for quick access to frequently used actions.
          </p>
        </div>
        <div>
          <div className="align-end flex w-full justify-end">
            <div className="justify center flex items-center">
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
                variant="primary"
                className="flex gap-2"
                onClick={handleRestore}
              >
                <ForwardedIconComponent name="RotateCcw" className="w-4" />
                Restore
              </Button>
            </div>
          </div>
        </div>
      </div>
      <div className="grid gap-6 pb-8">
        <div>
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
    </div>
  );
}
