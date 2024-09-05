import IconComponent from "../../../../components/genericIconComponent";
import { Button } from "../../../../components/ui/button";

import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
  usePatchGlobalVariables,
} from "@/controllers/API/queries/variables";
import { CellValueChangedEvent, ColDef, ColGroupDef, SelectionChangedEvent } from "ag-grid-community";
import { useState } from "react";
import GlobalVariableModal from "../../../../components/GlobalVariableModal/GlobalVariableModal";
import Dropdown from "../../../../components/dropdownComponent";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import TableComponent from "../../../../components/tableComponent";
import { Badge } from "../../../../components/ui/badge";
import useAlertStore from "../../../../stores/alertStore";
import TableAutoCellRender from "@/components/tableComponent/components/tableAutoCellRender";
import { GlobalVariable } from "@/types/global_variables";

export default function GlobalVariablesPage() {
  const setErrorData = useAlertStore((state) => state.setErrorData);
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
      headerName: "Variable Name",
      field: "name",
      flex: 2,
    }, //This column will be twice as wide as the others
    {
      headerName: "Type",
      field: "type",
      cellRenderer: BadgeRenderer,
      cellEditor: DropdownEditor,
      cellEditorParams: {
        options: ["Generic", "Credential"],
      },
      flex: 1,
    },
    {
      field: "value",
      cellRenderer:TableAutoCellRender
    },
    {
      headerName: "Apply To Fields",
      field: "default_fields",
      valueFormatter: (params) => {
        return params.value?.join(", ")??"";
      },
      flex: 1,
      resizable: false,
    },
  ]);

  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  const { data: globalVariables } = useGetGlobalVariables();
  const { mutate: mutateDeleteGlobalVariable } = useDeleteGlobalVariables();

  async function removeVariables() {
    selectedRows.map(async (row) => {
      const id = globalVariables?.find((variable) => variable.name === row)?.id;
      mutateDeleteGlobalVariable(
        { id },
        {
          onError: () => {
            setErrorData({
              title: `Error deleting variable`,
              list: [`ID not found for variable: ${row}`],
            });
          },
        },
      );
    });
  }
  const {mutate:updateVariable} = usePatchGlobalVariables();

  function handleUpdate(event:CellValueChangedEvent<GlobalVariable, any>) {
    const {data} = event;
    console.log(data);
    updateVariable(data);
  }

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <div className="flex w-full items-start justify-between gap-6">
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
          <GlobalVariableModal asChild>
            <Button data-testid="api-key-button-store" variant="primary">
              <IconComponent name="Plus" className="w-4" />
              Add New
            </Button>
          </GlobalVariableModal>
        </div>
      </div>

      <div className="flex h-full w-full flex-col justify-between">
        <TableComponent
          key={"globalVariables"}
          overlayNoRowsTemplate="No data available"
          onSelectionChanged={(event: SelectionChangedEvent) => {
            setSelectedRows(event.api.getSelectedRows().map((row) => row.name));
          }}
          rowSelection="multiple"
          onRowDoubleClicked={(event)=>{
            console.log(event);
          }}
          suppressRowClickSelection={true}
          pagination={true}
          columnDefs={colDefs}
          rowData={globalVariables ?? []}
          onDelete={removeVariables}
        />
      </div>
    </div>
  );
}
