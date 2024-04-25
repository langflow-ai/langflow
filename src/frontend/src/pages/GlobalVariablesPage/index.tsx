import IconComponent from "../../components/genericIconComponent";
import { Button } from "../../components/ui/button";

import TableComponent from "../../components/tableComponent";

export default function GlobalVariablesPage() {
  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="text-xl font-bold tracking-tight">Global Variables</h2>
          <p className="text-muted-foreground">
            Manage and assign global variables to default fields. You can add
            new global variables by clicking the button.
          </p>
        </div>
        <div className="flex-shrink-0">
          <Button data-testid="api-key-button-store" variant="primary">
            <IconComponent name="Plus" className="mr-2 w-4" />
            Add Global Variables
          </Button>
        </div>
      </div>

      <div className="flex h-full w-full flex-col justify-between">
        <TableComponent />
      </div>
    </div>
  );
}
