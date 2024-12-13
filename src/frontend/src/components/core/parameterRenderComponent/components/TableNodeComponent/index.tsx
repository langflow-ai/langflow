import TableModal from "@/modals/tableModal";
import { FormatColumns, generateBackendColumnsFromValue } from "@/utils/utils";
import { DataTypeDefinition, SelectionChangedEvent } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { cloneDeep } from "lodash";
import { useMemo, useRef, useState } from "react";
import { ForwardedIconComponent } from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { InputProps, TableComponentType } from "../../types";

export default function TableNodeComponent({
  tableTitle,
  description,
  value,
  editNode = false,
  id = "",
  columns,
  handleOnNewValue,
  disabled = false,
  table_options,
  trigger_icon = "Table",
  trigger_text = "Open Table",
}: InputProps<any[], TableComponentType>): JSX.Element {
  const dataTypeDefinitions: {
    [cellDataType: string]: DataTypeDefinition<any>;
  } = useMemo(() => {
    return {
      // override `date` to handle custom date format `dd/mm/yyyy`
      date: {
        baseDataType: "date",
        extendsDataType: "date",
        valueParser: (params) => {
          if (params.newValue == null) {
            return null;
          }
          // convert from `dd/mm/yyyy`
          const dateParts = params.newValue.split("/");
          return dateParts.length === 3
            ? new Date(
                parseInt(dateParts[2]),
                parseInt(dateParts[1]) - 1,
                parseInt(dateParts[0]),
              )
            : null;
        },
        valueFormatter: (params) => {
          let date = params.value;
          if (typeof params.value === "string") {
            date = new Date(params.value);
          }
          // convert to `dd/mm/yyyy`
          return date == null
            ? "‎"
            : `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}`;
        },
      },
      number: {
        baseDataType: "number",
        extendsDataType: "number",
        valueFormatter: (params) =>
          params.value == null ? "‎" : `${params.value}`,
      },
    };
  }, []);
  const [selectedNodes, setSelectedNodes] = useState<Array<any>>([]);
  const agGrid = useRef<AgGridReact>(null);
  const componentColumns = columns
    ? columns
    : generateBackendColumnsFromValue(value ?? [], table_options);
  const AgColumns = FormatColumns(componentColumns);
  function setAllRows() {
    if (agGrid.current && !agGrid.current.api.isDestroyed()) {
      const rows: any = [];
      agGrid.current.api.forEachNode((node) => rows.push(node.data));
      handleOnNewValue({ value: rows });
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
      handleOnNewValue({ value: [...value, ...toDuplicate] });
    }
  }
  function addRow() {
    const newRow = {};
    componentColumns.forEach((column) => {
      newRow[column.name] = column.default ?? null; // Use the default value if available
    });
    handleOnNewValue({ value: [...value, newRow] });
  }

  function updateComponent() {
    setAllRows();
  }
  const editable = componentColumns
    .map((column) => {
      const isCustomEdit =
        column.formatter &&
        ((column.formatter === "text" && column.edit_mode !== "inline") ||
          column.formatter === "json");
      return {
        field: column.name,
        onUpdate: updateComponent,
        editableCell: isCustomEdit ? false : true,
      };
    })
    .filter(
      (col) =>
        columns?.find((c) => c.name === col.field)?.disable_edit !== true,
    );

  return (
    <div
      className={
        "flex w-full items-center" + (disabled ? " cursor-not-allowed" : "")
      }
    >
      <div className="flex w-full items-center gap-3" data-testid={"div-" + id}>
        <TableModal
          tableOptions={table_options}
          dataTypeDefinitions={dataTypeDefinitions}
          autoSizeStrategy={{ type: "fitGridWidth", defaultMinWidth: 100 }}
          tableTitle={tableTitle}
          description={description}
          ref={agGrid}
          onSelectionChanged={(event: SelectionChangedEvent) => {
            setSelectedNodes(event.api.getSelectedNodes());
          }}
          rowSelection={table_options?.block_select ? undefined : "multiple"}
          suppressRowClickSelection={true}
          editable={editable}
          pagination={!table_options?.hide_options}
          addRow={addRow}
          onDelete={deleteRow}
          onDuplicate={duplicateRow}
          displayEmptyAlert={false}
          className="h-full w-full"
          columnDefs={AgColumns}
          rowData={value}
          context={{ field_parsers: table_options?.field_parsers }}
        >
          <Button
            disabled={disabled}
            variant="primary"
            size={editNode ? "xs" : "default"}
            className={
              "w-full " +
              (disabled ? "pointer-events-none cursor-not-allowed" : "")
            }
          >
            <ForwardedIconComponent
              name={trigger_icon}
              className="mt-px h-4 w-4"
            />
            <span className="font-normal">{trigger_text}</span>
          </Button>
        </TableModal>
      </div>
    </div>
  );
}
