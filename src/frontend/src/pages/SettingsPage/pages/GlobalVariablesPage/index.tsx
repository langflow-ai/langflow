import IconComponent from "../../../../components/genericIconComponent";
import { Button } from "../../../../components/ui/button";

import { ColDef, ColGroupDef, SelectionChangedEvent } from "ag-grid-community";
import { useEffect, useState } from "react";
import AddNewVariableButton from "../../../../components/addNewVariableButtonComponent/addNewVariableButton";
import Dropdown from "../../../../components/dropdownComponent";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import TableComponent from "../../../../components/tableComponent";
import { Badge } from "../../../../components/ui/badge";
import { useGlobalVariablesStore } from "../../../../stores/globalVariables";
import { cn } from "../../../../utils/utils";

export default function GlobalVariablesPage() {
  const globalVariablesEntries = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries
  );
  const removeGlobalVariable = useGlobalVariablesStore(
    (state) => state.removeGlobalVariable
  );
  const globalVariables = useGlobalVariablesStore(
    (state) => state.globalVariables
  );

  const BadgeRenderer = (props) => {
    return props.value !== "" ? (
      <div>
        <Badge variant="outline" size="md" className="font-normal">
          {props.value}
        </Badge>
      </div>
    ) : (
      <div></div>
    );
  };

  const [rowData, setRowData] =
    useState<
      {
        type: string | undefined;
        id: string;
        name: string;
        default_fields: string | undefined;
      }[]
    >();

  useEffect(() => {
    const rows: Array<{
      type: string | undefined;
      id: string;
      name: string;
      default_fields: string | undefined;
    }> = [];
    globalVariablesEntries.forEach((e) => {
      const globalVariableObj = globalVariables[e];
      rows.push({
        type: globalVariableObj.type,
        id: globalVariableObj.id,
        default_fields: (globalVariableObj.default_fields ?? []).join(", "),
        name: e,
      });
    });
    setRowData(rows);
  }, [globalVariables]);

  const DropdownEditor = ({ options, value, onValueChange }) => {
    return (
      <Dropdown options={options} value={value} onSelect={onValueChange}>
        <div className="-mt-1.5 w-full"></div>
      </Dropdown>
    );
  };
  // Column Definitions: Defines the columns to be displayed.
  const [colDefs, setColDefs] = useState<(ColDef<any> | ColGroupDef<any>)[]>([
    {
      headerCheckboxSelection: true,
      checkboxSelection: true,
      showDisabledCheckboxes: true,
      headerName: "Variable Name",
      field: "name",
      flex: 1,
    }, //This column will be twice as wide as the others
    {
      field: "type",
      cellRenderer: BadgeRenderer,
      cellEditor: DropdownEditor,
      cellEditorParams: {
        options: ["Generic", "Credential"],
      },
      flex: 1,
      editable: false,
    },
    // {
    //   field: "value",
    //   cellEditor: "agLargeTextCellEditor",
    //   flex: 2,
    //   editable: false,
    // },
    {
      headerName: "Apply To Fields",
      field: "default_fields",
      flex: 1,
      editable: false,
    },
  ]);

  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  function removeVariables() {
    selectedRows.forEach((row) => {
      removeGlobalVariable(row);
    });
  }

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Global Variables
            <ForwardedIconComponent
              name="Globe"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage global variables and assign them to fields.
          </p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <Button
            data-testid="api-key-button-store"
            variant="primary"
            className="group px-2"
            disabled={selectedRows.length === 0}
            onClick={removeVariables}
          >
            <IconComponent
              name="Trash2"
              className={cn(
                "h-5 w-5 text-destructive group-disabled:text-primary"
              )}
            />
          </Button>
          <AddNewVariableButton>
            <Button data-testid="api-key-button-store" variant="primary">
              <IconComponent name="Plus" className="mr-2 w-4" />
              Add New
            </Button>
          </AddNewVariableButton>
        </div>
      </div>

      <div className="flex h-full w-full flex-col justify-between pb-8">
        <TableComponent
          onSelectionChanged={(event: SelectionChangedEvent) => {
            setSelectedRows(event.api.getSelectedRows().map((row) => row.name));
          }}
          rowSelection="multiple"
          suppressRowClickSelection={true}
          columnDefs={colDefs}
          rowData={rowData}
        />
      </div>
    </div>
  );
}
