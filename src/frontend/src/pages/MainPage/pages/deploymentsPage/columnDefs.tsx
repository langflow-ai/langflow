import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type DeploymentRow = {
  id: string;
  name: string;
  type: string;
  deploymentType: "agent" | "mcp";
  mode?: string;
};

type BuildDeploymentColumnDefsParams = {
  onTestAgent: (deployment: {
    id: string;
    name: string;
    deploymentType: "agent" | "mcp";
    mode?: string;
  }) => void;
};

export const buildDeploymentColumnDefs = ({
  onTestAgent,
}: BuildDeploymentColumnDefsParams) => [
  {
    headerName: "Name",
    field: "name",
    flex: 3,
    cellRenderer: (params: { value: string }) => (
      <div className="flex min-w-0 flex-col justify-center gap-0.5 py-2">
        <span
          className="truncate text-sm font-medium leading-tight"
          title={params.value}
        >
          {params.value}
        </span>
      </div>
    ),
  },
  {
    headerName: "Type",
    field: "type",
    flex: 1,
    cellRenderer: (params: { value: string }) => {
      const isMcp = params.value === "MCP";
      const badgeClass = isMcp
        ? "border-border bg-muted text-muted-foreground"
        : "border-border bg-muted text-fuchsia-700 dark:text-fuchsia-400";

      return (
        <div className="flex items-center">
          <span
            className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium ${badgeClass}`}
          >
            {isMcp ? (
              <ForwardedIconComponent name="Mcp" className="h-3 w-3" />
            ) : (
              <ForwardedIconComponent name="Bot" className="h-3 w-3" />
            )}
            {params.value}
          </span>
        </div>
      );
    },
  },
  {
    headerName: "Environment",
    field: "mode",
    flex: 1,
    cellRenderer: (params: { value: string }) => {
      const isLive = params.value?.toLowerCase() === "live";
      const badgeClass = isLive
        ? "border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400"
        : "border-yellow-500/30 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400";

      return (
        <div className="flex items-center">
          <span
            className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${badgeClass}`}
          >
            {params.value}
          </span>
        </div>
      );
    },
  },
  {
    headerName: "Attached",
    field: "attached",
    flex: 1,
    cellRenderer: (params: { value: number }) => (
      <span className="text-sm text-muted-foreground">
        {params.value} {params.value === 1 ? "item" : "items"}
      </span>
    ),
  },
  {
    headerName: "Last Modified",
    field: "modifiedDate",
    flex: 1.5,
    headerClass: "[&_.ag-header-cell-resize]:hidden",
    cellRenderer: (params: {
      value: string;
      data: { createdDate: string };
    }) => (
      <div className="flex flex-col justify-center gap-0.5 py-2">
        <span className="text-sm leading-tight">{params.value}</span>
        <span className="text-xs text-muted-foreground">
          Created: {params.data.createdDate}
        </span>
      </div>
    ),
  },
  {
    headerName: "",
    field: "actions",
    width: 48,
    sortable: false,
    filter: false,
    resizable: false,
    cellRenderer: (params: { data?: DeploymentRow }) => (
      <div className="flex h-full items-center justify-end">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              unstyled
              className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <ForwardedIconComponent
                name="EllipsisVertical"
                className="h-4 w-4"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44">
            {params.data?.type !== "MCP" && (
              <>
                <DropdownMenuItem
                  className="gap-2"
                  onClick={() => {
                    if (!params.data) {
                      return;
                    }
                    onTestAgent({
                      id: params.data.id,
                      name: params.data.name,
                      deploymentType: params.data.deploymentType,
                      mode: params.data.mode,
                    });
                  }}
                >
                  <ForwardedIconComponent name="Bot" className="h-4 w-4" />
                  Test Agent
                </DropdownMenuItem>
                <DropdownMenuSeparator />
              </>
            )}
            <DropdownMenuItem className="gap-2">
              <ForwardedIconComponent name="Copy" className="h-4 w-4" />
              Duplicate
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2">
              <ForwardedIconComponent name="Pencil" className="h-4 w-4" />
              Update
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2 text-destructive focus:text-destructive">
              <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    ),
  },
];
