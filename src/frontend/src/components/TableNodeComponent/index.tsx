import TableModal from "@/modals/tableModal";
import { FormatColumns, generateBackendColumnsFromValue } from "@/utils/utils";
import { SelectionChangedEvent } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import { useRef, useState } from "react";
import { ForwardedIconComponent } from "../../components/genericIconComponent";
import { TableComponentType } from "../../types/components";
import { Button } from "../ui/button";

export default function TableNodeComponent({
  tableTitle,
  description,
  value,
  onChange,
  editNode = false,
  id = "",
  columns,
}: TableComponentType): JSX.Element {
  const [selectedNodes, setSelectedNodes] = useState<Array<any>>([]);
  const agGrid = useRef<AgGridReact>(null);
  const componentColumns = columns
    ? columns
    : generateBackendColumnsFromValue(value ?? []);

  const AgColumns = FormatColumns(componentColumns);
  function setAllRows() {
    if (agGrid.current) {
      const rows: any = [];
      agGrid.current.api.forEachNode((node) => rows.push(node.data));
      onChange(rows);
    }
  }
  function deleteRow() {
    if (agGrid.current && selectedNodes.length > 0) {
      agGrid.current.api.applyTransaction({
        remove: selectedNodes.map((node) => node.data),
      });
      setSelectedNodes([]);
      setAllRows();
    }
  }
  function duplicateRow() {
    if (agGrid.current && selectedNodes.length > 0) {
      const toDuplicate = selectedNodes.map((node) => cloneDeep(node.data));
      setSelectedNodes([]);
      const rows: any = [];
      onChange([...value, ...toDuplicate]);
    }
  }
  function addRow() {
    const newRow = {};
    componentColumns.forEach((column) => {
      newRow[column.name] = null;
    });
    onChange([...value, newRow]);
  }

  function updateComponente() {
    setAllRows();
  }
  const editable = componentColumns.map((column) => {
    const isCustomEdit =
      column.formatter &&
      (column.formatter === "text" || column.formatter === "json");
    return {
      field: column.name,
      onUpdate: updateComponente,
      editableCell: isCustomEdit ? false : true,
    };
  });

  return (
    <div className={"flex w-full items-center"}>
      <div className="flex w-full items-center gap-3" data-testid={"div-" + id}>
        <TableModal
          autoSizeStrategy={{ type: "fitGridWidth", defaultMinWidth: 100 }}
          tableTitle={tableTitle}
          description={description}
          ref={agGrid}
          onSelectionChanged={(event: SelectionChangedEvent) => {
            setSelectedNodes(event.api.getSelectedNodes());
          }}
          rowSelection="multiple"
          suppressRowClickSelection={true}
          editable={editable}
          pagination={true}
          addRow={addRow}
          onDelete={deleteRow}
          onDuplicate={duplicateRow}
          displayEmptyAlert={false}
          className="h-full w-full"
          columnDefs={AgColumns}
          rowData={value}
        >
          <Button
            variant="primary"
            size={editNode ? "xs" : "default"}
            className="w-full"
          >
            <ForwardedIconComponent name="Table" className="mt-px h-4 w-4" />
            <span className="font-normal">Open Table</span>
          </Button>
        </TableModal>
      </div>
    </div>
  );
}
