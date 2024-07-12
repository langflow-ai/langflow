import BaseModal from "@/modals/baseModal";
import { FormatColumns } from "@/utils/utils";
import { SelectionChangedEvent } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useRef, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { TableComponentType } from "../../types/components";
import TableComponent from "../tableComponent";

export default function TableNodeComponent({
  tableTitle,
  value,
  onChange,
  editNode = false,
  id = "",
  columns,
}: TableComponentType): JSX.Element {
  const [selectedNodes, setSelectedNodes] = useState<Array<any>>([]);
  const agGrid = useRef<AgGridReact>(null);
  const AgColumns = FormatColumns(columns);
  function deleteRow() {
    if (agGrid.current && selectedNodes.length > 0) {
      agGrid.current.api.applyTransaction({
        remove: selectedNodes.map((node) => node.data),
      });
      setSelectedNodes([]);

      const rows: any = [];
      agGrid.current.api.forEachNode((node) => rows.push(node.data));
      onChange(rows);
    }
  }
  function duplicateRow() {}
  function addRow() {
    const newRow = {};
    columns.forEach((column) => {
      newRow[column.name] = null;
    });
    onChange([...value, newRow]);
  }

  function editRow() {}

  return (
    <div className={"flex w-full items-center"}>
      <div className="flex w-full items-center gap-3" data-testid={"div-" + id}>
        <BaseModal>
          <BaseModal.Header description={"Add or edit your data"}>
            <IconComponent name="Table" />
            {tableTitle}
          </BaseModal.Header>
          <BaseModal.Content>
            <TableComponent
              ref={agGrid}
              onSelectionChanged={(event: SelectionChangedEvent) => {
                setSelectedNodes(event.api.getSelectedNodes());
              }}
              rowSelection="multiple"
              suppressRowClickSelection={true}
              editable={true}
              pagination={true}
              addRow={addRow}
              onDelete={deleteRow}
              onDuplicate={duplicateRow}
              displayEmptyAlert={false}
              className="h-full w-full"
              columnDefs={AgColumns}
              rowData={value}
            ></TableComponent>
          </BaseModal.Content>
          <BaseModal.Footer submit={{ label: "close" }}></BaseModal.Footer>
          <BaseModal.Trigger>
            <div className="flex items-start justify-between align-middle">
              <span>Edit Data</span>
            </div>
          </BaseModal.Trigger>
        </BaseModal>
      </div>
    </div>
  );
}
