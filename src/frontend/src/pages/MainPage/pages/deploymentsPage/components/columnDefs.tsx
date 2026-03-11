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
  url: string;
  type: string;
  deploymentType: "agent" | "mcp";
  mode?: string;
  status: "Production" | "Draft";
  health: "Healthy" | "Pending" | "Unhealthy";
  endpoint: string;
  attached: number;
  modifiedDate: string;
  modifiedBy: string;
};

type BuildDeploymentColumnDefsParams = {
  onTestAgent: (deployment: {
    id: string;
    name: string;
    deploymentType: "agent" | "mcp";
    mode?: string;
  }) => void;
};

const HEALTH_DOT_COLOR: Record<string, string> = {
  Healthy: "bg-green-500",
  Pending: "bg-yellow-400",
  Unhealthy: "bg-red-500",
};

const STATUS_BADGE_CLASS: Record<string, string> = {
  Production: "border-blue-500/30 bg-blue-500/15 text-blue-400",
  Draft: "border-zinc-500/30 bg-zinc-500/15 text-zinc-400",
};

export const buildDeploymentColumnDefs = ({
  onTestAgent,
}: BuildDeploymentColumnDefsParams) => [
  {
    headerName: "Name",
    field: "name",
    flex: 2,
    cellRenderer: (params: { value: string; data: DeploymentRow }) => (
      <div className="flex min-w-0 flex-col justify-center gap-0.5 py-2">
        <span
          className="truncate text-sm font-medium leading-tight"
          title={params.value}
        >
          {params.value}
        </span>
        <span
          className="truncate text-xs text-muted-foreground"
          title={params.data.url}
        >
          {params.data.url}
        </span>
      </div>
    ),
  },
  {
    headerName: "Status",
    field: "status",
    flex: 1,
    cellRenderer: (params: { value: string }) => {
      const badgeClass =
        STATUS_BADGE_CLASS[params.value] ?? STATUS_BADGE_CLASS.Draft;

      return (
        <div className="flex items-center">
          <span
            className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-medium ${badgeClass}`}
          >
            {params.value}
          </span>
        </div>
      );
    },
  },
  {
    headerName: "Health",
    field: "health",
    flex: 1,
    cellRenderer: (params: { value: string }) => {
      const dotColor = HEALTH_DOT_COLOR[params.value] ?? "bg-muted-foreground";

      return (
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${dotColor}`} />
          <span className="text-sm">{params.value}</span>
        </div>
      );
    },
  },
  {
    headerName: "Attached",
    field: "attached",
    flex: 0.8,
    cellRenderer: (params: { value: number }) => (
      <span className="text-sm text-muted-foreground">
        {params.value} {params.value === 1 ? "item" : "items"}
      </span>
    ),
  },
  {
    headerName: "Endpoint",
    field: "endpoint",
    flex: 2,
    cellRenderer: (params: { value: string }) => (
      <span
        className="truncate text-sm text-muted-foreground"
        title={params.value}
      >
        {params.value}
      </span>
    ),
  },
  {
    headerName: "Last Modified",
    field: "modifiedDate",
    flex: 1.2,
    cellRenderer: (params: { value: string; data: { modifiedBy: string } }) => (
      <div className="flex flex-col justify-center gap-0.5 py-2">
        <span className="text-sm font-medium leading-tight">
          {params.value}
        </span>
        <span className="text-xs text-muted-foreground">
          by {params.data.modifiedBy}
        </span>
      </div>
    ),
  },
  {
    headerName: "Test",
    field: "test",
    width: 60,
    sortable: false,
    filter: false,
    resizable: false,
    cellRenderer: (params: { data?: DeploymentRow }) => (
      <div className="flex h-full items-center justify-center">
        <Button
          unstyled
          className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
          onClick={() => {
            if (!params.data) return;
            onTestAgent({
              id: params.data.id,
              name: params.data.name,
              deploymentType: params.data.deploymentType,
              mode: params.data.mode,
            });
          }}
        >
          <ForwardedIconComponent name="Play" className="h-4 w-4" />
        </Button>
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
