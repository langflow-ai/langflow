import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const MOCK_DEPLOYMENTS = [
  {
    name: "Production Sales Agent",
    url: "https://api.production.example.com/sales-agent",
    type: "Agent",
    status: "Healthy",
    attached: 2,
    configs: [{ id: "SALES_BOT_PROD", count: 3 }],
    modifiedDate: "2026-02-15",
    modifiedBy: "Sarah Han",
  },
  {
    name: "Test Environment Sales Agent",
    url: "https://api.staging.example.com/sales-agent",
    type: "Agent",
    status: "Healthy",
    attached: 1,
    configs: [{ id: "SALES_BOT_STAGING", count: 2 }],
    modifiedDate: "2026-02-18",
    modifiedBy: "Sarah Han",
  },
  {
    name: "Customer Support MCP",
    url: "https://api.dev.example.com/customer-support",
    type: "MCP",
    status: "Pending",
    attached: 1,
    configs: [{ id: "CUSTOMER_SUPPORT_PROD", count: null }],
    modifiedDate: "2026-02-19",
    modifiedBy: "Sarah Han",
  },
  {
    name: "Multi-Config Sales Pipeline",
    url: "https://api.dev.example.com/multi-config",
    type: "Agent",
    status: "Unhealthy",
    attached: 3,
    configs: [
      { id: "SALES_BOT_PROD", count: 3 },
      { id: "SALES_BOT_STAGING", count: 2 },
    ],
    modifiedDate: "2026-02-08",
    modifiedBy: "Sarah Han",
  },
];

const STATUS_DOT: Record<string, string> = {
  Healthy: "bg-green-500",
  Pending: "bg-yellow-400",
  Unhealthy: "bg-red-500",
};

const columnDefs = [
  {
    headerName: "Name",
    field: "name",
    flex: 3,
    cellRenderer: (params: any) => (
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
    cellRenderer: (params: any) => (
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
    cellRenderer: (params: any) => (
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
    cellRenderer: (params: any) => (
      <span className="text-sm text-muted-foreground">
        {params.value} {params.value === 1 ? "item" : "items"}
      </span>
    ),
  },
  {
    headerName: "Config (AppID)",
    field: "configs",
    flex: 2,
    cellRenderer: (params: any) => (
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
    cellRenderer: (params: any) => (
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

const TOGGLE_OPTIONS = ["All Deployments", "Deployment Provider"] as const;
type DeploymentView = (typeof TOGGLE_OPTIONS)[number];

const DeploymentsTab = () => {
  const [activeView, setActiveView] =
    useState<DeploymentView>("All Deployments");

  return (
    <div className="flex h-full flex-col p-5">
      <div className="flex justify-between items-center">
        <div className="relative flex h-9 items-center rounded-lg border border-border bg-background p-1">
          <div
            className="absolute h-7 rounded-md bg-muted shadow-sm transition-all duration-200"
            style={{
              width: activeView === "All Deployments" ? 133 : 165,
              left: activeView === "All Deployments" ? "4px" : 137,
            }}
          />
          {TOGGLE_OPTIONS.map((option) => (
            <button
              key={option}
              onClick={() => setActiveView(option)}
              className={`relative z-10 flex-1 whitespace-nowrap rounded-md px-3 py-1 text-center text-sm font-medium transition-colors ${
                activeView === option
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
        <Button className="flex items-center gap-2 font-semibold">
          <ForwardedIconComponent name="Plus" /> New Deployment
        </Button>
      </div>

      <div className="flex h-full flex-col pt-4">
        <div className="relative h-full">
          <TableComponent
            rowHeight={65}
            cellSelection={false}
            tableOptions={{ hide_options: true }}
            columnDefs={columnDefs}
            rowData={MOCK_DEPLOYMENTS}
            className="w-full ag-no-border"
            pagination
            quickFilterText=""
            gridOptions={{
              ensureDomOrder: true,
              colResizeDefault: "shift",
            }}
          />
        </div>
      </div>
    </div>
  );
};

export default DeploymentsTab;
