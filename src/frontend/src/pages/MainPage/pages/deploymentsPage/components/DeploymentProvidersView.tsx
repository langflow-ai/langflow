import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import type { DeploymentProvider } from "@/controllers/API/queries/deployments/use-deployments";
import { cn } from "@/utils/utils";

const STATUS_COLOR: Record<string, string> = {
  Connected: "text-green-500",
  Error: "text-red-500",
  Pending: "text-yellow-400",
};

const STATUS_DOT_COLOR: Record<string, string> = {
  Connected: "bg-green-500",
  Error: "bg-red-500",
  Pending: "bg-yellow-400",
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

type ProviderStatus = "Connected" | "Error" | "Pending";

type MockProviderCard = {
  id: string;
  providerName: string;
  providerKey: string;
  status: ProviderStatus;
  endpoint: string;
  lastVerified: string;
  deployments: number;
  actionLabel: string;
  iconName: string;
};

const MOCK_PROVIDER_CARDS: MockProviderCard[] = [
  {
    id: "langflow-cloud",
    providerName: "Langflow Cloud",
    providerKey: "langflow",
    status: "Connected",
    endpoint: "https://cloud.langflow.io",
    lastVerified: "6 days ago",
    deployments: 12,
    actionLabel: "Test Connection",
    iconName: "Cloud",
  },
  {
    id: "watsonx-orchestrate",
    providerName: "watsonx Orchestrate",
    providerKey: "watsonx",
    status: "Connected",
    endpoint: "https://api.watsonx-orchestrate.ibm.com/instance",
    lastVerified: "6 days ago",
    deployments: 8,
    actionLabel: "Test Connection",
    iconName: "WatsonxOrchestrate",
  },
  {
    id: "aws-cloud-deploy",
    providerName: "AWS Cloud Deploy",
    providerKey: "cloud",
    status: "Error",
    endpoint: "https://aws.example.com",
    lastVerified: "6 days ago",
    deployments: 3,
    actionLabel: "Reconnect",
    iconName: "Cloud",
  },
  {
    id: "azure-functions",
    providerName: "Azure Functions",
    providerKey: "cloud",
    status: "Connected",
    endpoint: "https://azure-functions.microsoft.com",
    lastVerified: "6 days ago",
    deployments: 5,
    actionLabel: "Test Connection",
    iconName: "Cloud",
  },
];

type MockDeploymentConfigRow = {
  id: string;
  name: string;
  description: string;
  usedBy: string;
  created: string;
};

const MOCK_DEPLOYMENT_CONFIG_ROWS: MockDeploymentConfigRow[] = [
  {
    id: "standard-production-config",
    name: "Standard Production Config",
    description: "Default configuration for production workloads",
    usedBy: "15 deployments",
    created: "Jan 14, 2026",
  },
  {
    id: "test-environment-config",
    name: "Test Environment Config",
    description: "Lightweight configuration for testing environments",
    usedBy: "8 deployments",
    created: "Jan 19, 2026",
  },
  {
    id: "high-performance-config",
    name: "High Performance Config",
    description: "Enhanced configuration for high-load workloads",
    usedBy: "3 deployments",
    created: "Jan 31, 2026",
  },
];

type DeploymentProvidersViewProps = {
  providers: DeploymentProvider[];
  deploymentRows: DeploymentListRow[];
  selectedProviderId: string | null;
  onSelectProvider: (providerId: string) => void;
  onConfigureProvider: (provider: DeploymentProvider) => void;
  selectedProviderDeploymentCount: number;
  isLoadingDeployments: boolean;
  isLoadingProviders: boolean;
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onTestAgent: (deployment: {
    id: string;
    name: string;
    deploymentType: "agent" | "mcp";
    mode?: string;
  }) => void;
  onCreateDeployment?: () => void;
  activeSubTab?: "deployments" | "providers";
};

export type DeploymentListRow = {
  id: string;
  name: string;
  url: string;
  type: string;
  deploymentType: "agent" | "mcp";
  mode: string;
  status: "Production" | "Draft";
  health: "Healthy" | "Pending" | "Unhealthy";
  endpoint: string;
  attached: number;
  modifiedDate: string;
  modifiedBy: string;
  createdDate: string;
};

const MOCK_DEPLOYMENT_ROWS: DeploymentListRow[] = [
  {
    id: "1",
    name: "Production Main Deployment",
    url: "https://api.production.example.com",
    type: "Agent",
    deploymentType: "agent",
    mode: "live",
    status: "Production",
    health: "Healthy",
    endpoint: "https://api.production.example.com",
    attached: 3,
    modifiedDate: "2026-02-09",
    modifiedBy: "Sarah Han",
    createdDate: "2026-01-15",
  },
  {
    id: "2",
    name: "Test Environment A",
    url: "https://api.staging.example.com",
    type: "Agent",
    deploymentType: "agent",
    mode: "draft",
    status: "Draft",
    health: "Healthy",
    endpoint: "https://api.staging.example.com",
    attached: 3,
    modifiedDate: "2026-02-08",
    modifiedBy: "Sarah Han",
    createdDate: "2026-01-20",
  },
  {
    id: "3",
    name: "Staging Environment",
    url: "https://api.dev.example.com",
    type: "MCP",
    deploymentType: "mcp",
    mode: "draft",
    status: "Draft",
    health: "Pending",
    endpoint: "https://api.dev.example.com",
    attached: 2,
    modifiedDate: "2026-02-10",
    modifiedBy: "Sarah Han",
    createdDate: "2026-02-01",
  },
  {
    id: "4",
    name: "Development Instance",
    url: "https://api.dev.example.com",
    type: "Agent",
    deploymentType: "agent",
    mode: "draft",
    status: "Draft",
    health: "Unhealthy",
    endpoint: "https://api.dev.example.com",
    attached: 1,
    modifiedDate: "2026-02-06",
    modifiedBy: "Sarah Han",
    createdDate: "2026-02-03",
  },
];

const DEPLOYMENT_SKELETON_ROWS = 6;

const DeploymentsTableSkeleton = () => {
  return (
    <div className="w-full rounded-md border border-border">
      <div className="grid grid-cols-[2fr_1fr_1fr_0.8fr_2fr_1.2fr_60px_48px] gap-4 border-b border-border px-4 py-3">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-14" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-8" />
        <Skeleton className="h-4 w-4" />
      </div>
      {Array.from({ length: DEPLOYMENT_SKELETON_ROWS }).map((_, index) => (
        <div
          key={`deployment-skeleton-row-${index}`}
          className={`grid grid-cols-[2fr_1fr_1fr_0.8fr_2fr_1.2fr_60px_48px] items-center gap-4 px-4 py-4 ${
            index < DEPLOYMENT_SKELETON_ROWS - 1 ? "border-b border-border" : ""
          }`}
        >
          <div className="flex flex-col gap-1">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-48" />
          </div>
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-14" />
          <Skeleton className="h-4 w-48" />
          <div className="flex flex-col gap-1">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-3 w-16" />
          </div>
          <Skeleton className="h-4 w-8" />
          <Skeleton className="h-4 w-4" />
        </div>
      ))}
    </div>
  );
};

export const DeploymentProvidersView = ({
  providers: _providers,
  deploymentRows,
  selectedProviderId: _selectedProviderId,
  onSelectProvider: _onSelectProvider,
  onConfigureProvider: _onConfigureProvider,
  selectedProviderDeploymentCount: _selectedProviderDeploymentCount,
  isLoadingDeployments,
  isLoadingProviders: _isLoadingProviders,
  page: _page,
  pageSize: _pageSize,
  total: _total,
  onPageChange: _onPageChange,
  onTestAgent,
  onCreateDeployment,
  activeSubTab = "deployments",
}: DeploymentProvidersViewProps) => {
  const rowsToRender =
    deploymentRows.length > 0 ? deploymentRows : MOCK_DEPLOYMENT_ROWS;
  const deploymentTableGridCols =
    "grid-cols-[minmax(0,2.4fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,2fr)_minmax(0,1.2fr)_2.5rem_2rem]";

  return (
    <div className="flex h-full min-h-0 flex-col gap-6 pb-4">
      {/* Provider Cards Grid */}
      {activeSubTab === "providers" && (
        <div className="flex flex-col gap-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {MOCK_PROVIDER_CARDS.map((provider) => (
              <div
                key={provider.id}
                className="flex flex-col gap-4 rounded-xl border border-border/70 bg-background p-5 text-left"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={cn(
                      "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                      provider.providerKey === "watsonx"
                        ? "bg-transparent"
                        : "bg-zinc-700",
                    )}
                  >
                    {provider.providerKey === "langflow" ? (
                      <LangflowLogo className="h-5 w-5 text-white" />
                    ) : (
                      <ForwardedIconComponent
                        name={provider.iconName}
                        className={
                          provider.providerKey === "watsonx"
                            ? "h-7 w-7 object-contain"
                            : "h-5 w-5 text-white"
                        }
                      />
                    )}
                  </div>
                  <div className="min-w-0 w-full">
                    <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
                      <span className="text-sm font-semibold leading-tight">
                        {provider.providerName}
                      </span>
                      <span className="flex items-center gap-1">
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${
                            STATUS_DOT_COLOR[provider.status] ??
                            "bg-muted-foreground"
                          }`}
                        />
                        <span className="text-xs pl-1">{provider.status}</span>
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {provider.providerKey}
                    </span>
                  </div>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-xs text-muted-foreground">
                    Endpoint
                  </span>
                  <span className="truncate text-sm">{provider.endpoint}</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs text-muted-foreground">
                      Last Verified
                    </span>
                    <span className="text-sm">{provider.lastVerified}</span>
                  </div>
                  <div className="flex flex-col gap-0.5 text-right">
                    <span className="text-xs text-muted-foreground">
                      Deployments
                    </span>
                    <span className="text-sm">{provider.deployments}</span>
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-8 flex-1 gap-1.5 text-xs"
                  >
                    <ForwardedIconComponent
                      name="Settings"
                      className="h-3.5 w-3.5"
                    />
                    Configure
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-8 flex-1 gap-1.5 text-xs"
                  >
                    <ForwardedIconComponent
                      name={
                        provider.status === "Error"
                          ? "RefreshCw"
                          : "CircleCheck"
                      }
                      className="h-3.5 w-3.5"
                    />
                    {provider.actionLabel}
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <div>
            <h3 className="text-xl font-semibold">Deployment Configurations</h3>
            <div className="mt-4">
              <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,2fr)_minmax(0,1.2fr)_minmax(0,1.2fr)_2rem] items-center gap-4 px-4 py-4 text-xs font-medium text-muted-foreground">
                <span>Name</span>
                <span>Description</span>
                <span>Used By</span>
                <span>Created</span>
                <span />
              </div>
              <div className="mt-1 border-y border-border/70">
                {MOCK_DEPLOYMENT_CONFIG_ROWS.map((row) => (
                  <div
                    key={row.id}
                    className="grid w-full grid-cols-[minmax(0,2fr)_minmax(0,2fr)_minmax(0,1.2fr)_minmax(0,1.2fr)_2rem] items-center gap-4 border-b border-border/60 px-4 py-5 text-left transition-colors hover:bg-muted/20 last:border-b-0"
                  >
                    <span className="truncate text-sm font-medium">
                      {row.name}
                    </span>
                    <span className="truncate text-sm text-muted-foreground">
                      {row.description}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {row.usedBy}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {row.created}
                    </span>
                    <div className="flex items-center justify-end">
                      <Button
                        unstyled
                        className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        <ForwardedIconComponent
                          name="EllipsisVertical"
                          className="h-4 w-4"
                        />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Deployments Table */}
      {activeSubTab === "deployments" && (
        <div className="flex-1 min-h-0 rounded-lg">
          <div className="flex h-full min-h-0 flex-col">
            <div
              className={cn(
                "grid items-center gap-4 px-4 py-4 text-xs font-medium text-muted-foreground",
                deploymentTableGridCols,
              )}
            >
              <span className="pl-3">Name</span>
              <span>Status</span>
              <span>Health</span>
              <span>Attached</span>
              <span>Endpoint</span>
              <span>Last Modified</span>
              <span>Test</span>
              <span />
            </div>

            <div className="mt-1 border-y border-border/70">
              <div className="max-h-[calc(100vh-360px)] overflow-auto">
                {isLoadingDeployments ? (
                  <DeploymentsTableSkeleton />
                ) : rowsToRender.length === 0 ? (
                  <div className="flex min-h-52 flex-col items-center justify-center gap-3 px-4 py-6 text-sm text-muted-foreground">
                    <span>No deployments found.</span>
                    {onCreateDeployment && (
                      <Button size="sm" onClick={onCreateDeployment}>
                        Create deployment
                      </Button>
                    )}
                  </div>
                ) : (
                  rowsToRender.map((deployment) => {
                    const healthColor =
                      HEALTH_DOT_COLOR[deployment.health] ??
                      "bg-muted-foreground";
                    const badgeClass =
                      STATUS_BADGE_CLASS[deployment.status] ??
                      STATUS_BADGE_CLASS.Draft;

                    return (
                      <div
                        key={deployment.id}
                        className={cn(
                          "grid w-full items-center gap-4 border-b border-border/60 px-4 py-5 text-left transition-colors hover:bg-muted/20 last:border-b-0",
                          deploymentTableGridCols,
                        )}
                      >
                        <div className="flex min-w-0 flex-col gap-0.5 pl-3">
                          <span
                            className="truncate text-sm font-medium leading-tight"
                            title={deployment.name}
                          >
                            {deployment.name}
                          </span>
                          <span
                            className="truncate text-xs text-muted-foreground"
                            title={deployment.url}
                          >
                            {deployment.url}
                          </span>
                        </div>

                        <div className="flex items-center">
                          <span
                            className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-medium ${badgeClass}`}
                          >
                            {deployment.status}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span
                            className={`h-2 w-2 rounded-full ${healthColor}`}
                          />
                          <span className="text-sm">{deployment.health}</span>
                        </div>

                        <span className="text-sm text-muted-foreground">
                          {deployment.attached}{" "}
                          {deployment.attached === 1 ? "item" : "items"}
                        </span>

                        <span
                          className="truncate text-sm text-muted-foreground"
                          title={deployment.endpoint}
                        >
                          {deployment.endpoint}
                        </span>

                        <div className="flex flex-col gap-0.5">
                          <span className="text-sm font-medium leading-tight">
                            {deployment.modifiedDate}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            by {deployment.modifiedBy}
                          </span>
                        </div>

                        <div className="flex items-center justify-center">
                          <Button
                            unstyled
                            className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
                            onClick={() => {
                              onTestAgent({
                                id: deployment.id,
                                name: deployment.name,
                                deploymentType: deployment.deploymentType,
                                mode: deployment.mode,
                              });
                            }}
                          >
                            <ForwardedIconComponent
                              name="Play"
                              className="h-4 w-4"
                            />
                          </Button>
                        </div>

                        <div className="flex items-center justify-end">
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
                              {deployment.type !== "MCP" && (
                                <>
                                  <DropdownMenuItem
                                    className="gap-2"
                                    onClick={() => {
                                      onTestAgent({
                                        id: deployment.id,
                                        name: deployment.name,
                                        deploymentType:
                                          deployment.deploymentType,
                                        mode: deployment.mode,
                                      });
                                    }}
                                  >
                                    <ForwardedIconComponent
                                      name="Bot"
                                      className="h-4 w-4"
                                    />
                                    Test Agent
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                </>
                              )}
                              <DropdownMenuItem className="gap-2">
                                <ForwardedIconComponent
                                  name="Copy"
                                  className="h-4 w-4"
                                />
                                Duplicate
                              </DropdownMenuItem>
                              <DropdownMenuItem className="gap-2">
                                <ForwardedIconComponent
                                  name="Pencil"
                                  className="h-4 w-4"
                                />
                                Update
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem className="gap-2 text-destructive focus:text-destructive">
                                <ForwardedIconComponent
                                  name="Trash2"
                                  className="h-4 w-4"
                                />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
