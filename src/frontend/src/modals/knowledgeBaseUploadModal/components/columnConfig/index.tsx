import type { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import { useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import TableModal from "@/modals/tableModal";
import type { ColumnField } from "@/types/utils/functions";
import { FormatterType } from "@/types/utils/functions";
import { FormatColumns } from "@/utils/utils";
import type { ColumnConfigRow } from "../../types";

const COLUMN_CONFIG_COLUMNS: ColumnField[] = [
  {
    name: "column_name",
    display_name: "Column Name",
    sortable: true,
    filterable: true,
    formatter: FormatterType.text,
    description: "Name of the column in the source DataFrame",
    edit_mode: "inline",
  },
  {
    name: "vectorize",
    display_name: "Vectorize",
    sortable: false,
    filterable: false,
    formatter: FormatterType.boolean,
    description: "Create embeddings for this column",
    default: false,
    edit_mode: "inline",
  },
  {
    name: "identifier",
    display_name: "Identifier",
    sortable: false,
    filterable: false,
    formatter: FormatterType.boolean,
    description: "Use this column as unique identifier",
    default: false,
    edit_mode: "inline",
  },
];

interface ColumnConfigProps {
  columnConfig: ColumnConfigRow[];
  onColumnConfigChange: (value: ColumnConfigRow[]) => void;
}

export function ColumnConfig({
  columnConfig,
  onColumnConfigChange,
}: ColumnConfigProps) {
  const AgColumns = FormatColumns(COLUMN_CONFIG_COLUMNS);
  const agGrid = useRef<AgGridReact>(null);
  const [isTableModalOpen, setIsTableModalOpen] = useState(false);
  const [tempColumnConfig, setTempColumnConfig] = useState<ColumnConfigRow[]>(
    cloneDeep(columnConfig),
  );

  function setAllRows() {
    if (agGrid.current && !agGrid.current.api.isDestroyed()) {
      const rows: ColumnConfigRow[] = [];
      agGrid.current.api.forEachNode((node) => rows.push(node.data));
      setTempColumnConfig(rows);
    }
  }

  function addRow() {
    setTempColumnConfig([
      ...tempColumnConfig,
      { column_name: "", vectorize: false, identifier: false },
    ]);
  }

  function deleteRow() {
    if (agGrid.current) {
      const selectedNodes = agGrid.current.api.getSelectedNodes();
      if (selectedNodes.length > 0) {
        agGrid.current.api.applyTransaction({
          remove: selectedNodes.map((node) => node.data),
        });
        setAllRows();
      }
    }
  }

  function duplicateRow() {
    if (agGrid.current) {
      const selectedNodes = agGrid.current.api.getSelectedNodes();
      if (selectedNodes.length > 0) {
        const toDuplicate = selectedNodes.map((node) => cloneDeep(node.data));
        setTempColumnConfig([...tempColumnConfig, ...toDuplicate]);
      }
    }
  }

  function handleTableSave() {
    setAllRows();
    if (agGrid.current && !agGrid.current.api.isDestroyed()) {
      const rows: ColumnConfigRow[] = [];
      agGrid.current.api.forEachNode((node) => rows.push(node.data));
      onColumnConfigChange(rows);
    } else {
      onColumnConfigChange(tempColumnConfig);
    }
    setIsTableModalOpen(false);
  }

  function handleTableCancel() {
    setTempColumnConfig(cloneDeep(columnConfig));
    setIsTableModalOpen(false);
  }

  const editable = COLUMN_CONFIG_COLUMNS.map((column) => ({
    field: column.name,
    onUpdate: () => setAllRows(),
    editableCell: true,
  }));

  return (
    <TableModal
      open={isTableModalOpen}
      setOpen={(open) => {
        if (open) {
          setTempColumnConfig(cloneDeep(columnConfig));
        }
        setIsTableModalOpen(open);
      }}
      tableTitle="Column Configuration"
      description="Configure column behavior for the knowledge base."
      ref={agGrid}
      onSelectionChanged={() => {}}
      rowSelection="multiple"
      editable={editable}
      pagination={true}
      addRow={addRow}
      onDelete={deleteRow}
      onDuplicate={duplicateRow}
      displayEmptyAlert={false}
      className="h-full w-full"
      columnDefs={AgColumns}
      rowData={tempColumnConfig}
      stopEditingWhenCellsLoseFocus={true}
      autoSizeStrategy={{
        type: "fitGridWidth",
        defaultMinWidth: 100,
      }}
      onSave={handleTableSave}
      onCancel={handleTableCancel}
    >
      <Button variant="outline" className="w-full justify-center">
        <span className="flex items-center gap-2">
          <ForwardedIconComponent name="Columns" className="h-4 w-4" />
          Open Table
        </span>
      </Button>
    </TableModal>
  );
}
