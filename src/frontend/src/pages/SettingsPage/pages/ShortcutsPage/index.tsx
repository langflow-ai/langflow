import type { ColDef } from "ag-grid-community";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toCamelCase } from "@/utils/utils";
import ForwardedIconComponent from "../../../../components/common/genericIconComponent";
import TableComponent from "../../../../components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "../../../../components/ui/button";
import { defaultShortcuts } from "../../../../constants/constants";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import SettingsPageHeader from "../../components/SettingsPageHeader";
import CellRenderShortcuts from "./CellRenderWrapper";
import EditShortcutButton from "./EditShortcutButton";

export default function ShortcutsPage() {
  const { t } = useTranslation();
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const setShortcuts = useShortcutsStore((state) => state.setShortcuts);

  // Column Definitions: Defines the columns to be displayed.
  const colDefs: ColDef[] = [
    {
      headerName: t("shortcuts.columnFunctionality"),
      field: "display_name",
      flex: 1,
      editable: false,
      resizable: false,
      valueFormatter: (params) =>
        t(`shortcuts.name.${toCamelCase(params.data.name)}`, {
          defaultValue: params.value,
        }),
    }, //This column will be twice as wide as the others
    {
      headerName: t("shortcuts.columnKeyboardShortcut"),
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

  function openShortcutEditor(shortcutName: string) {
    setSelectedRows([shortcutName]);
    setOpen(true);
  }

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <SettingsPageHeader
        title={t("shortcuts.title")}
        description={t("shortcuts.description")}
      >
        {open && (
          <EditShortcutButton
            disable={selectedRows.length === 0}
            shortcut={selectedRows}
            shortcuts={shortcuts}
            defaultShortcuts={defaultShortcuts}
            open={open}
            setOpen={setOpen}
            setSelected={setSelectedRows}
          >
            <div style={{ display: "none" }} />
          </EditShortcutButton>
        )}
        <Button size="sm" className="gap-2" onClick={handleRestore}>
          <ForwardedIconComponent name="RotateCcw" className="w-4" />
          {t("shortcuts.restoreButton")}
        </Button>
      </SettingsPageHeader>
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
                openShortcutEditor(e.data.name);
              }}
              onCellKeyDown={(e) => {
                const event = e.event as KeyboardEvent | undefined;
                if (event?.key !== "Enter" && event?.key !== " ") {
                  return;
                }
                event.preventDefault();
                openShortcutEditor(e.data.name);
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
