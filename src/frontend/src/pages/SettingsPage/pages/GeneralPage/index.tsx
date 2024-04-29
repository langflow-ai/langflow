import { Button } from "../../../../components/ui/button";

import { ColDef, ColGroupDef } from "ag-grid-community";
import { useState } from "react";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../../../components/ui/card";
import { Checkbox } from "../../../../components/ui/checkbox";
import { Input } from "../../../../components/ui/input";

export default function GeneralPage() {
  // Column Definitions: Defines the columns to be displayed.
  const [colDefs, setColDefs] = useState<(ColDef<any> | ColGroupDef<any>)[]>([
    { headerName: "Variable Name", field: "name", flex: 1 }, //This column will be twice as wide as the others
    {
      field: "type",
      cellEditor: "agSelectCellEditor",
      cellEditorParams: {
        values: ["Prompt", "Credential"],
        valueListGap: 10,
      },
      flex: 1,
      editable: true,
    },
    {
      field: "value",
      cellEditor: "agLargeTextCellEditor",
      cellEditorPopup: true,
      flex: 2,
      editable: true,
    },
    {
      headerName: "Apply To Fields",
      field: "defaultFields",
      flex: 1,
      editable: true,
    },
  ]);

  const [rowData, setRowData] = useState([
    {
      name: "OpenAI Key",
      type: "Credential",
      value: "apijpioj09u302j0982ejf",
      defaultFields: "Open AI API Key",
    },
    {
      name: "Prompt",
      type: "Prompt",
      value: `Answer user's questions based on the document below:

    ---
    
    {Document}
    
    ---
    
    Question:
    {Question}
    
    Answer:
    `,
      defaultFields: ["Prompt"],
    },
    {
      name: "Azure Key",
      type: "Credential",
      value: "awowkdenvoaimojndofunoweoij0293u0n2e08n23",
      defaultFields: ["Azure API Key"],
    },
  ]);

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            General
            <ForwardedIconComponent
              name="SlidersHorizontal"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage settings related to Langflow and your account.
          </p>
        </div>
      </div>

      <div className="grid gap-6">
        <Card x-chunk="dashboard-04-chunk-1">
          <CardHeader>
            <CardTitle>Store Name</CardTitle>
            <CardDescription>
              Used to identify your store in the marketplace.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form>
              <Input placeholder="Store Name" />
            </form>
          </CardContent>
          <CardFooter className="border-t px-6 py-4">
            <Button>Save</Button>
          </CardFooter>
        </Card>
        <Card x-chunk="dashboard-04-chunk-2">
          <CardHeader>
            <CardTitle>Plugins Directory</CardTitle>
            <CardDescription>
              The directory within your project, in which your plugins are
              located.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="flex flex-col gap-4">
              <Input
                placeholder="Project Name"
                defaultValue="/content/plugins"
              />
              <div className="flex items-center space-x-2">
                <Checkbox id="include" defaultChecked />
                <label
                  htmlFor="include"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Allow administrators to change the directory.
                </label>
              </div>
            </form>
          </CardContent>
          <CardFooter className="border-t px-6 py-4">
            <Button>Save</Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
