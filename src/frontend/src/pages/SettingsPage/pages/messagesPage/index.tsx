import IconComponent from "../../../../components/genericIconComponent";
import { Button } from "../../../../components/ui/button";

import { ColDef, ColGroupDef, SelectionChangedEvent } from "ag-grid-community";
import { useEffect, useState } from "react";
import AddNewVariableButton from "../../../../components/addNewVariableButtonComponent/addNewVariableButton";
import Dropdown from "../../../../components/dropdownComponent";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import TableComponent from "../../../../components/tableComponent";
import { Badge } from "../../../../components/ui/badge";
import { Card, CardContent } from "../../../../components/ui/card";
import {
  deleteGlobalVariable,
  getMessagesTable,
} from "../../../../controllers/API";
import useAlertStore from "../../../../stores/alertStore";
import { useGlobalVariablesStore } from "../../../../stores/globalVariablesStore/globalVariables";
import { cn } from "../../../../utils/utils";

export default function MessagesPage() {
  const [columns, setColumns] = useState<Array<ColDef | ColGroupDef>>([]);
  const [rows, setRows] = useState<any>([]);
  const removeGlobalVariable = useGlobalVariablesStore(
    (state) => state.removeGlobalVariable,
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getVariableId = useGlobalVariablesStore((state) => state.getVariableId);

  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  async function removeVariables() {
    const deleteGlobalVariablesPromise = selectedRows.map(async (row) => {
      const id = getVariableId(row);
      const deleteGlobalVariables = deleteGlobalVariable(id!);
      await deleteGlobalVariables;
    });
    Promise.all(deleteGlobalVariablesPromise)
      .then(() => {
        selectedRows.forEach((row) => {
          removeGlobalVariable(row);
        });
      })
      .catch(() => {
        setErrorData({
          title: `Error deleting global variables.`,
        });
      });
  }

  useEffect(() => {
    console.log("MessagesPage useEffect");
    getMessagesTable("union").then((data) => {
      const { columns, rows } = data;
      console.log(data);
      setColumns(columns.map((col) => ({ ...col, editable: true })));
      setRows(rows);
    });
  }, []);

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Messages
            <ForwardedIconComponent
              name="MessagesSquare"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage your messages as you like.
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
                "h-5 w-5 text-destructive group-disabled:text-primary",
              )}
            />
          </Button>
        </div>
      </div>

      <div className="flex h-full w-full flex-col justify-between pb-8">
        <Card x-chunk="dashboard-04-chunk-2" className="h-full pt-4">
          <CardContent className="h-full">
            <TableComponent
              overlayNoRowsTemplate="No data available"
              onSelectionChanged={(event: SelectionChangedEvent) => {
                setSelectedRows(
                  event.api.getSelectedRows().map((row) => row.name),
                );
              }}
              rowSelection="multiple"
              suppressRowClickSelection={true}
              pagination={true}
              columnDefs={columns}
              rowData={rows}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
