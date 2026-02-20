import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { STATUS_DOT } from "./constants";

export const columnDefs = [
  {
    headerName: "Name",
    field: "name",
    flex: 3,
    cellRenderer: (params: { value: string; data: { url: string } }) => (
      <div className="flex flex-col justify-center gap-0.5 py-2">
        <span className="text-sm font-medium leading-tight">
          {params.value}
        </span>
        <span className="truncate text-xs text-muted-foreground">
          {params.data.url}
        </span>
      </div>
    ),
  },
  {
    headerName: "Type",
    field: "type",
    flex: 1,
    cellRenderer: (params: { value: string }) => (
      <div className="flex items-center">
        <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
          {params.value === "MCP" ? (
            <ForwardedIconComponent name="Mcp" className="h-3 w-3" />
          ) : (
            <ForwardedIconComponent name="Bot" className="h-3 w-3" />
          )}
          {params.value}
        </span>
      </div>
    ),
  },
  {
    headerName: "Status",
    field: "status",
    flex: 1,
    cellRenderer: (params: { value: string }) => (
      <div className="flex items-center gap-1.5">
        <span
          className={`h-2 w-2 rounded-full ${STATUS_DOT[params.value] ?? "bg-muted-foreground"}`}
        />
        <span className="text-sm">{params.value}</span>
      </div>
    ),
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
    headerName: "Config (AppID)",
    field: "configs",
    flex: 2,
    cellRenderer: (params: {
      value: { id: string; count: number | null }[];
    }) => (
      <div className="flex h-full flex-col items-start justify-center gap-1">
        {params.value.map(
          (cfg: { id: string; count: number | null }, i: number) => (
            <div key={i} className="flex items-center gap-1">
              <span className="inline-flex w-fit items-center rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                {cfg.id}
              </span>
              {cfg.count !== null && (
                <span className="text-xs text-muted-foreground">
                  ({cfg.count})
                </span>
              )}
            </div>
          ),
        )}
      </div>
    ),
  },
  {
    headerName: "Last Modified",
    field: "modifiedDate",
    flex: 1.5,
    headerClass: "[&_.ag-header-cell-resize]:hidden",
    cellRenderer: (params: { value: string; data: { modifiedBy: string } }) => (
      <div className="flex flex-col justify-center gap-0.5 py-2">
        <span className="text-sm leading-tight">{params.value}</span>
        <span className="text-xs text-muted-foreground">
          by {params.data.modifiedBy}
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
    cellRenderer: () => (
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
