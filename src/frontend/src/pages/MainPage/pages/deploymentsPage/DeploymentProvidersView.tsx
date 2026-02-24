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
import type {
  DeploymentConfigItem,
  DeploymentProvider,
} from "@/controllers/API/queries/deployments/use-deployments";

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
  configurations: DeploymentConfigItem[];
  selectedProviderId: string | null;
  onSelectProvider: (providerId: string) => void;
  onConfigureProvider: (provider: DeploymentProvider) => void;
  selectedProviderDeploymentCount: number;
  isLoadingProviders: boolean;
  isLoadingConfigurations: boolean;
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
  configurations,
  selectedProviderId,
  onSelectProvider,
  onConfigureProvider,
  selectedProviderDeploymentCount,
  isLoadingProviders,
  isLoadingConfigurations,
}: DeploymentProvidersViewProps) => {
  return (
    <div className="flex flex-col gap-6 pb-4">
      {/* Provider Cards Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {providers.map((provider) => {
          const isSelected = selectedProviderId === provider.id;
          const status = provider.has_api_key ? "Connected" : "Error";
          const providerName = normalizeProviderLabel(provider.provider_key);
          const iconName =
            provider.provider_key === "watsonx-orchestrate" ? "IBM" : "Cloud";

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
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-700">
                  {provider.provider_key === "langflow" ? (
                    <LangflowLogo className="h-5 w-5 text-white" />
                  ) : (
                    <ForwardedIconComponent
                      name={iconName}
                      className="h-5 w-5 text-white"
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
                    {formatDate(provider.updated_at || provider.registered_at)}
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
                {status === "Error" ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-8 flex-1 gap-1.5 text-xs"
                  >
                    <ForwardedIconComponent
                      name="RefreshCcw"
                      className="h-3.5 w-3.5"
                    />
                    Reconnect
                  </Button>
                ) : (
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
                )}
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

      {/* Deployment Configurations */}
      <div className="flex flex-col gap-3">
        <h2 className="text-base font-semibold">Deployment Configurations</h2>
        <div className="rounded-lg ">
          {/* Table Header */}
          <div className="grid grid-cols-[2fr_3fr_1.5fr_1.5fr_40px] border-b border-border px-4 py-2.5">
            <span className="text-xs font-medium text-muted-foreground">
              Name
            </span>
            <span className="text-xs font-medium text-muted-foreground">
              Description
            </span>
            <span className="text-xs font-medium text-muted-foreground">
              Used By
            </span>
            <span className="text-xs font-medium text-muted-foreground">
              Created
            </span>
            <span />
          </div>

          {/* Table Rows */}
          {configurations.map((config, i) => (
            <div
              key={config.id}
              className={`grid grid-cols-[2fr_3fr_1.5fr_1.5fr_40px] items-center px-4 py-3 ${
                i < configurations.length - 1 ? "border-b border-border" : ""
              }`}
            >
              <span className="text-sm font-semibold">{config.name}</span>
              <span className="truncate pr-4 text-sm text-muted-foreground">
                {config.description || "No description"}
              </span>
              <span className="text-sm text-muted-foreground">—</span>
              <span className="text-sm text-muted-foreground">
                {config.provider_data?.environment?.toString() || "draft"}
              </span>
              <div className="flex justify-end">
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
                      <ForwardedIconComponent
                        name="Pencil"
                        className="h-4 w-4"
                      />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem className="gap-2">
                      <ForwardedIconComponent name="Copy" className="h-4 w-4" />
                      Duplicate
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
          ))}
          {!isLoadingConfigurations && configurations.length === 0 && (
            <div className="px-4 py-4 text-sm text-muted-foreground">
              No deployment configurations found for the selected provider.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
