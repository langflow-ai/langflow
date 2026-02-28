import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { DeploymentProvider } from "@/controllers/API/queries/deployments/use-deployments";
import { buildDeploymentColumnDefs } from "./columnDefs";

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
};

export type DeploymentListRow = {
  id: string;
  name: string;
  url: string;
  type: string;
  deploymentType: "agent" | "mcp";
  mode: string;
  attached: number;
  modifiedDate: string;
  createdDate: string;
};

const DEPLOYMENT_SKELETON_ROWS = 6;

const DeploymentsTableSkeleton = () => {
  return (
    <div className="w-full rounded-md border border-border">
      <div className="grid grid-cols-[2fr_2fr_1fr_1fr_1.5fr_1.5fr] gap-4 border-b border-border px-4 py-3">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-14" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-20" />
      </div>
      {Array.from({ length: DEPLOYMENT_SKELETON_ROWS }).map((_, index) => (
        <div
          key={`deployment-skeleton-row-${index}`}
          className={`grid grid-cols-[2fr_2fr_1fr_1fr_1.5fr_1.5fr] items-center gap-4 px-4 py-4 ${
            index < DEPLOYMENT_SKELETON_ROWS - 1 ? "border-b border-border" : ""
          }`}
        >
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-14" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
        </div>
      ))}
    </div>
  );
};

const formatDate = (date: string | null): string => {
  if (!date) {
    return "Not verified";
  }

  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) {
    return "Not verified";
  }

  return parsed.toLocaleDateString();
};

const normalizeProviderLabel = (providerKey: string): string => {
  if (providerKey === "watsonx-orchestrate") {
    return "watsonx Orchestrate";
  }

  return providerKey
    .split("-")
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
};

export const DeploymentProvidersView = ({
  providers,
  deploymentRows,
  selectedProviderId,
  onSelectProvider,
  onConfigureProvider,
  selectedProviderDeploymentCount,
  isLoadingDeployments,
  isLoadingProviders,
  page,
  pageSize,
  total,
  onPageChange,
  onTestAgent,
}: DeploymentProvidersViewProps) => {
  const deploymentColumnDefs = buildDeploymentColumnDefs({ onTestAgent });
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="flex flex-col gap-6 pb-4">
      {/* Provider Cards Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {providers.map((provider) => {
          const isSelected = selectedProviderId === provider.id;
          const status = "Connected";
          const providerName = normalizeProviderLabel(provider.provider_key);
          const iconName =
            provider.provider_key === "watsonx-orchestrate"
              ? "WatsonxOrchestrate"
              : "Cloud";

          return (
            <button
              type="button"
              key={provider.id}
              onClick={() => onSelectProvider(provider.id)}
              className={`flex flex-col gap-4 rounded-xl border bg-card p-5 text-left transition-colors ${
                isSelected
                  ? "border-primary"
                  : "border-border hover:border-muted-foreground"
              }`}
            >
              {/* Card Header */}
              <div className="flex items-start gap-3">
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                    provider.provider_key === "watsonx-orchestrate"
                      ? "bg-transparent"
                      : "bg-zinc-700"
                  }`}
                >
                  {provider.provider_key === "langflow" ? (
                    <LangflowLogo className="h-5 w-5 text-white" />
                  ) : (
                    <ForwardedIconComponent
                      name={iconName}
                      className={
                        provider.provider_key === "watsonx-orchestrate"
                          ? "h-7 w-7 object-contain"
                          : "h-5 w-5 text-white"
                      }
                    />
                  )}
                </div>
                <div className="min-w-0 w-full">
                  <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
                    <span className="text-sm font-semibold leading-tight">
                      {providerName}
                    </span>
                    <span className="flex items-center gap-1">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT_COLOR[status] ?? "bg-muted-foreground"}`}
                      />
                      <span
                        className={`text-xs ${STATUS_COLOR[status] ?? "text-muted-foreground"}`}
                      >
                        {status}
                      </span>
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {provider.account_id || provider.provider_key}
                  </span>
                </div>
              </div>

              {/* Endpoint */}
              <div className="flex flex-col gap-0.5">
                <span className="text-xs text-muted-foreground">Endpoint</span>
                <span className="truncate text-sm">{provider.backend_url}</span>
              </div>

              {/* Stats Row */}
              <div className="grid grid-cols-2 gap-2">
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs text-muted-foreground">
                    Last Verified
                  </span>
                  <span className="text-sm">
                    {formatDate(provider.registered_at)}
                  </span>
                </div>
                <div className="flex flex-col gap-0.5 text-right">
                  <span className="text-xs text-muted-foreground">
                    Deployments
                  </span>
                  <span className="text-sm">
                    {isSelected ? selectedProviderDeploymentCount : "—"}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-8 flex-1 gap-1.5 text-xs"
                  onClick={(event) => {
                    event.stopPropagation();
                    onConfigureProvider(provider);
                  }}
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
                    name="CircleCheck"
                    className="h-3.5 w-3.5"
                  />
                  Test Connection
                </Button>
              </div>
            </button>
          );
        })}
        {!isLoadingProviders && providers.length === 0 && (
          <div className="col-span-full rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
            No deployment providers found. Add a provider to start using
            deployments.
          </div>
        )}
      </div>

      {/* Provider Resource List */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Deployments</h2>
          <div className="flex items-center gap-2 text-sm">
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange(Math.max(1, page - 1))}
            >
              Prev
            </Button>
            <span className="text-muted-foreground">
              Page {page} / {totalPages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            >
              Next
            </Button>
          </div>
        </div>

        <div className="rounded-lg">
          <>
            <div className="relative h-[560px]">
              {isLoadingDeployments ? (
                <DeploymentsTableSkeleton />
              ) : (
                <TableComponent
                  rowHeight={65}
                  cellSelection={false}
                  tableOptions={{ hide_options: true }}
                  columnDefs={deploymentColumnDefs}
                  rowData={deploymentRows}
                  className="w-full ag-no-border"
                  pagination={false}
                  quickFilterText=""
                  gridOptions={{
                    ensureDomOrder: true,
                    colResizeDefault: "shift",
                    domLayout: "normal",
                  }}
                />
              )}
            </div>
            {!isLoadingDeployments && deploymentRows.length === 0 && (
              <div className="px-1 pt-3 text-sm text-muted-foreground">
                No deployments found for the selected provider.
              </div>
            )}
          </>
        </div>
      </div>
    </div>
  );
};
