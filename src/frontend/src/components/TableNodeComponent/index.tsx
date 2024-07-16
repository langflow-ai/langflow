import BaseModal from "@/modals/baseModal";
import { FormatColumns } from "@/utils/utils";
import { SelectionChangedEvent } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import { useRef, useState } from "react";
import IconComponent, {
  ForwardedIconComponent,
} from "../../components/genericIconComponent";
import { TableComponentType } from "../../types/components";
import TableComponent from "../tableComponent";
import { Button } from "../ui/button";

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
    columns.forEach((column) => {
      newRow[column.name] = null;
    });
    onChange([...value, newRow]);
  }

  function updateComponente() {
    setAllRows();
  }
  const editable = columns.map((column) => {
    const is_text = column.formatter && column.formatter === "text";
    return {
      field: column.name,
      onUpdate: updateComponente,
      editableCell: is_text ? false : true,
    };
  });

  return (
    <div className={"flex w-full items-center"}>
      <div className="flex w-full items-center gap-3" data-testid={"div-" + id}>
        <BaseModal>
          <BaseModal.Header description={"Add or edit your data"}>
            <div className="flex justify-center gap-2 align-baseline">
              <IconComponent name="Table" />
              {tableTitle}
            </div>
          </BaseModal.Header>
          <BaseModal.Content>
            <TableComponent
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
            ></TableComponent>
          </BaseModal.Content>
          <BaseModal.Footer submit={{ label: "close" }}></BaseModal.Footer>
          <BaseModal.Trigger asChild>
            <Button variant="primary" className="w-full">
              <ForwardedIconComponent name="Table" className="mt-px h-4 w-4" />
              <span className="font-normal">Open Table</span>
            </Button>
          </BaseModal.Trigger>
        </BaseModal>
      </div>
    </div>
  );
}
