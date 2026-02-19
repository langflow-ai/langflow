import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { StepperModal, StepperModalFooter } from "@/modals/stepperModal";

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

const MOCK_FLOWS = [
  {
    id: "flow-1",
    name: "Qualify Lead",
    updatedDate: "2026-02-18",
    snapshotDate: "2026-02-17",
  },
  {
    id: "flow-2",
    name: "Summarize Call Notes",
    updatedDate: "2026-02-19",
    snapshotDate: "2026-02-18",
  },
  {
    id: "flow-3",
    name: "Create Ticket",
    updatedDate: "2026-02-16",
    snapshotDate: null,
  },
];

const MOCK_SNAPSHOTS = [
  { id: "snap-1", name: "Qualify Lead v1.2", updatedDate: "2026-02-17" },
  {
    id: "snap-2",
    name: "Summarize Call Notes v2.0",
    updatedDate: "2026-02-18",
  },
];

const ATTACH_TABS = ["Flows", "Snapshots"] as const;
type AttachTab = (typeof ATTACH_TABS)[number];

const DEPLOYMENT_TYPES = ["Agent", "MCP"] as const;
type DeploymentType = (typeof DEPLOYMENT_TYPES)[number];

const TOTAL_STEPS = 5;

const DeploymentsTab = () => {
  const [activeView, setActiveView] =
    useState<DeploymentView>("All Deployments");

  const [newDeploymentOpen, setNewDeploymentOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [deploymentType, setDeploymentType] = useState<DeploymentType>("Agent");
  const [deploymentName, setDeploymentName] = useState("");
  const [deploymentDescription, setDeploymentDescription] = useState("");
  const [deploymentUrl, setDeploymentUrl] = useState("");
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [attachTab, setAttachTab] = useState<AttachTab>("Flows");

  const handleBack = () => setCurrentStep((s) => Math.max(1, s - 1));
  const handleNext = () => setCurrentStep((s) => Math.min(TOTAL_STEPS, s + 1));
  const handleSubmit = () => {
    setNewDeploymentOpen(false);
    setCurrentStep(1);
    setDeploymentName("");
    setDeploymentDescription("");
    setDeploymentUrl("");
    setDeploymentType("Agent");
    setSelectedItems(new Set());
    setAttachTab("Flows");
  };
  const handleOpenChange = (open: boolean) => {
    setNewDeploymentOpen(open);
    if (!open) {
      setCurrentStep(1);
      setDeploymentName("");
      setDeploymentDescription("");
      setDeploymentUrl("");
      setDeploymentType("Agent");
      setSelectedItems(new Set());
      setAttachTab("Flows");
    }
  };

  const toggleItem = (id: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

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
        <Button
          className="flex items-center gap-2 font-semibold"
          onClick={() => setNewDeploymentOpen(true)}
        >
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
      <StepperModal
        open={newDeploymentOpen}
        onOpenChange={handleOpenChange}
        currentStep={currentStep}
        totalSteps={TOTAL_STEPS}
        title="Create Deployment"
        contentClassName="bg-secondary"
        icon="Rocket"
        description="Deploy your Langflow workflows to watsonx Orchestrate"
        showProgress
        width="w-[800px]"
        height="h-[618px]"
        size="medium-h-full"
        footer={
          <StepperModalFooter
            currentStep={currentStep}
            totalSteps={TOTAL_STEPS}
            onBack={handleBack}
            onNext={handleNext}
            onSubmit={handleSubmit}
            nextDisabled={
              (currentStep === 1 && !deploymentName.trim()) ||
              (currentStep === 2 && selectedItems.size === 0)
            }
            submitLabel="Create Deployment"
          />
        }
      >
        {currentStep === 1 && (
          <div className="flex h-full flex-col gap-5 overflow-y-auto">
            <div>
              <h3 className="text-base font-semibold">Deployment Basics</h3>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">
                Deployment Name <span className="text-destructive">*</span>
              </label>
              <Input
                placeholder="e.g., Production Sales Agent"
                value={deploymentName}
                onChange={(e) => setDeploymentName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Description</label>
              <Textarea
                placeholder="Describe what this deployment does..."
                value={deploymentDescription}
                onChange={(e) => setDeploymentDescription(e.target.value)}
                rows={4}
                className="resize-none placeholder:text-placeholder-foreground"
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">
                Deployment Type <span className="text-destructive">*</span>
              </label>
              <div className="grid grid-cols-2 gap-3">
                {(
                  [
                    {
                      type: "Agent" as DeploymentType,
                      label: "Agent",
                      icon: "Bot",
                      description:
                        "Conversational agent with chat interface and tool calling",
                    },
                    {
                      type: "MCP" as DeploymentType,
                      label: "MCP Server",
                      icon: "Mcp",
                      description:
                        "Model Context Protocol server for tool integration",
                    },
                  ] as const
                ).map(({ type, label, icon, description }) => (
                  <button
                    key={type}
                    onClick={() => setDeploymentType(type)}
                    className={`flex flex-col gap-2 rounded-xl border p-4 text-left transition-colors ${
                      deploymentType === type
                        ? "border-primary bg-background"
                        : "border-border hover:border-muted-foreground"
                    }`}
                  >
                    <div
                      className={`flex h-9 w-9 items-center justify-center rounded-md ${
                        deploymentType === type ? "bg-primary/10" : "bg-muted"
                      }`}
                    >
                      <ForwardedIconComponent
                        name={icon}
                        className={`h-5 w-5 ${
                          deploymentType === type
                            ? "text-primary"
                            : "text-muted-foreground"
                        }`}
                      />
                    </div>
                    <p className="text-sm font-semibold">{label}</p>
                    <p className="text-xs text-muted-foreground">
                      {description}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {currentStep === 2 && (
          <div className="flex h-full flex-col gap-4">
            <div>
              <h3 className="text-base font-semibold">
                Attach Flows or Snapshots
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Select one or more flows or snapshots to include in this
                deployment
              </p>
            </div>
            <div className="flex border-b border-border">
              {ATTACH_TABS.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setAttachTab(tab)}
                  className={`px-4 pb-2 text-sm font-medium transition-colors ${
                    attachTab === tab
                      ? "border-b-2 border-foreground text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
            <div className="flex flex-col gap-2 overflow-y-auto">
              {(attachTab === "Flows" ? MOCK_FLOWS : MOCK_SNAPSHOTS).map(
                (item) => (
                  <button
                    key={item.id}
                    onClick={() => toggleItem(item.id)}
                    className={`flex items-start gap-3 rounded-lg border bg-background p-3 text-left transition-colors ${
                      selectedItems.has(item.id)
                        ? "border-primary"
                        : "border-border hover:border-muted-foreground"
                    }`}
                  >
                    <Checkbox
                      checked={selectedItems.has(item.id)}
                      className="mt-0.5 pointer-events-none"
                    />
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold">
                          {item.name}
                        </span>
                        <span className="inline-flex items-center rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                          {attachTab === "Flows" ? "Flow" : "Snapshot"}
                        </span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        Last updated: {item.updatedDate}
                        {"snapshotDate" in item && item.snapshotDate
                          ? ` • Snapshot available (${item.snapshotDate})`
                          : ""}
                      </span>
                    </div>
                  </button>
                ),
              )}
            </div>
            {selectedItems.size === 0 && (
              <p className="mt-auto text-center text-sm text-muted-foreground">
                Select at least one flow or snapshot to continue
              </p>
            )}
          </div>
        )}

        {currentStep === 3 && (
          <div className="flex h-full flex-col gap-3">WIP 3</div>
        )}
        {currentStep === 4 && (
          <div className="flex h-full flex-col gap-3">WIP 4</div>
        )}
        {currentStep === 5 && (
          <div className="flex h-full flex-col gap-3">WIP 5</div>
        )}
      </StepperModal>
    </div>
  );
};

export default DeploymentsTab;
