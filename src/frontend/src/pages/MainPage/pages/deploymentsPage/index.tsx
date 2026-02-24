import { useEffect, useMemo, useState } from "react";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import {
  type DeploymentProvider,
  type DeploymentCreatePayload,
  useGetDeploymentConfigs,
  useGetDeployments,
  useGetDeploymentProviders,
  useGetDeploymentSnapshots,
  usePostCreateDeployment,
} from "@/controllers/API/queries/deployments/use-deployments";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StepperModal, StepperModalFooter } from "@/modals/stepperModal";
import useAlertStore from "@/stores/alertStore";
import type { FlowType } from "@/types/flow";
import { columnDefs } from "./columnDefs";
import { TOGGLE_OPTIONS, TOTAL_STEPS } from "./constants";
import { DeploymentProvidersView } from "./DeploymentProvidersView";
import { StepAttach } from "./steps/StepAttach";
import { StepBasics } from "./steps/StepBasics";
import { StepConfiguration } from "./steps/StepConfiguration";
import { StepReview } from "./steps/StepReview";
import { StepScope } from "./steps/StepScope";
import { useDeploymentForm } from "./useDeploymentForm";
import { ConfigureDeploymentProviderModal } from "./ConfigureDeploymentProviderModal";
import { RegisterDeploymentProviderModal } from "./RegisterDeploymentProviderModal";

type DeploymentTableRow = {
  name: string;
  url: string;
  type: string;
  status: string;
  attached: number;
  configs: { id: string; count: number | null }[];
  modifiedDate: string;
  modifiedBy: string;
};

const formatDateLabel = (value?: string | null): string => {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }

  return parsed.toLocaleDateString();
};

const mapModeToStatus = (mode?: string): string => {
  if (mode === "live" || mode === "both") {
    return "Healthy";
  }
  if (mode === "draft" || mode === "unknown" || !mode) {
    return "Pending";
  }
  return "Unhealthy";
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

const truncateAccountId = (value: string, prefixLength: number = 5): string => {
  if (value.length <= prefixLength) {
    return value;
  }
  return `${value.slice(0, prefixLength)}...`;
};

const getProviderAccountLabel = (provider: DeploymentProvider): string => {
  const providerLabel = normalizeProviderLabel(provider.provider_key);
  return provider.account_id
    ? `${providerLabel} (${truncateAccountId(provider.account_id)})`
    : providerLabel;
};

const ProviderOptionIcon = ({ provider }: { provider: DeploymentProvider }) => {
  if (provider.provider_key === "langflow") {
    return <LangflowLogo className="h-3.5 w-3.5 text-white" />;
  }

  return (
    <ForwardedIconComponent
      name={provider.provider_key === "watsonx-orchestrate" ? "IBM" : "Cloud"}
      className="h-3.5 w-3.5 text-white"
    />
  );
};

const buildRawFlowPayload = (flow: FlowType): Record<string, unknown> | null => {
  if (!flow.data) {
    return null;
  }

  return {
    id: flow.id,
    name: flow.name,
    description: flow.description || "",
    data: flow.data,
    tags: flow.tags || [],
  };
};

const DEPLOYMENT_SKELETON_ROWS = 6;

const DeploymentsTableSkeleton = () => {
  return (
    <div className="w-full rounded-md border border-border">
      <div className="grid grid-cols-[2fr_2fr_1fr_1fr_1fr_1.5fr_1.5fr] gap-4 border-b border-border px-4 py-3">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-14" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-20" />
      </div>
      {Array.from({ length: DEPLOYMENT_SKELETON_ROWS }).map((_, index) => (
        <div
          key={`deployment-skeleton-row-${index}`}
          className={`grid grid-cols-[2fr_2fr_1fr_1fr_1fr_1.5fr_1.5fr] items-center gap-4 px-4 py-4 ${
            index < DEPLOYMENT_SKELETON_ROWS - 1 ? "border-b border-border" : ""
          }`}
        >
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-14" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-8" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
        </div>
      ))}
    </div>
  );
};

const DeploymentsTab = () => {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(
    null,
  );
  const [registerProviderOpen, setRegisterProviderOpen] = useState(false);
  const [configureProviderOpen, setConfigureProviderOpen] = useState(false);
  const [providerToConfigure, setProviderToConfigure] =
    useState<DeploymentProvider | null>(null);

  const providersQuery = useGetDeploymentProviders({
    refetchOnWindowFocus: false,
  });
  const providers = providersQuery.data?.deployment_providers || [];
  const hasProviders = providers.length > 0;

  useEffect(() => {
    const selectedStillExists = selectedProviderId
      ? providers.some((provider) => provider.id === selectedProviderId)
      : false;

    if ((!selectedProviderId || !selectedStillExists) && providers.length > 0) {
      setSelectedProviderId(providers[0].id);
    }
    if (providers.length === 0) {
      setSelectedProviderId(null);
    }
  }, [providers, selectedProviderId]);

  const providerId = selectedProviderId || providers[0]?.id || "";
  const selectedProvider = providers.find((provider) => provider.id === providerId);
  const selectedProviderLabel = selectedProvider
    ? getProviderAccountLabel(selectedProvider)
    : "Select provider account";

  const handleConfigureProvider = (provider: DeploymentProvider) => {
    setProviderToConfigure(provider);
    setConfigureProviderOpen(true);
  };

  const deploymentsQuery = useGetDeployments(
    { providerId },
    {
      enabled: Boolean(providerId),
      refetchOnWindowFocus: false,
    },
  );
  const configsQuery = useGetDeploymentConfigs(
    { providerId },
    {
      enabled: Boolean(providerId),
      refetchOnWindowFocus: false,
    },
  );
  const snapshotsQuery = useGetDeploymentSnapshots(
    { providerId },
    {
      enabled: Boolean(providerId),
      refetchOnWindowFocus: false,
    },
  );
  const flowsQuery = useGetRefreshFlowsQuery(
    { get_all: true, header_flows: true },
    {
      refetchOnWindowFocus: false,
      enabled: true,
    },
  );
  const createDeploymentMutation = usePostCreateDeployment({ providerId });

  const liveDeployments = deploymentsQuery.data?.deployments || [];
  const deploymentConfigs = configsQuery.data?.configs || [];
  const deploymentSnapshots = snapshotsQuery.data?.snapshots || [];
  const flows = useMemo<FlowType[]>(() => {
    const data = flowsQuery.data;
    if (!data) {
      return [];
    }
    return Array.isArray(data) ? data : data.items;
  }, [flowsQuery.data]);

  const deploymentRows = useMemo<DeploymentTableRow[]>(() => {
    return liveDeployments.map((deployment) => {
      const snapshotIds =
        deployment.provider_data?.snapshot_ids &&
        Array.isArray(deployment.provider_data.snapshot_ids)
          ? deployment.provider_data.snapshot_ids
          : [];
      const mode = typeof deployment.provider_data?.mode === "string"
        ? deployment.provider_data.mode
        : undefined;

      return {
        name: deployment.name,
        url: `Deployment ID: ${deployment.id}`,
        type: deployment.type.toUpperCase() === "MCP" ? "MCP" : "Agent",
        status: mapModeToStatus(mode),
        attached: snapshotIds.length,
        configs: [],
        modifiedDate: "-",
        modifiedBy: "-",
      };
    });
  }, [liveDeployments]);

  const attachFlowItems = useMemo(
    () =>
      flows.map((flow) => ({
        id: flow.id,
        name: flow.name,
        updatedDate: formatDateLabel(flow.updated_at || flow.date_created || null),
        snapshotDate: null,
      })),
    [flows],
  );

  const attachSnapshotItems = useMemo(
    () =>
      deploymentSnapshots.map((snapshot) => ({
        id: snapshot.id,
        name: snapshot.name,
        updatedDate: "-",
      })),
    [deploymentSnapshots],
  );

  const {
    activeView,
    setActiveView,
    newDeploymentOpen,
    currentStep,
    deploymentType,
    setDeploymentType,
    deploymentName,
    setDeploymentName,
    deploymentDescription,
    setDeploymentDescription,
    selectedItems,
    attachTab,
    setAttachTab,
    configMode,
    setConfigMode,
    configName,
    setConfigName,
    keyFormat,
    setKeyFormat,
    envVars,
    setEnvVars,
    variableScope,
    setVariableScope,
    handleBack,
    handleNext,
    handleSubmit,
    handleOpenChange,
    toggleItem,
  } = useDeploymentForm();

  const selectedReviewItems = useMemo(() => {
    const selectedFlows = attachFlowItems
      .filter((item) => selectedItems.has(item.id))
      .map((item) => ({ name: item.name, kind: "Flow" as const }));
    const selectedSnapshots = attachSnapshotItems
      .filter((item) => selectedItems.has(item.id))
      .map((item) => ({ name: item.name, kind: "Snapshot" as const }));

    return [...selectedFlows, ...selectedSnapshots];
  }, [attachFlowItems, attachSnapshotItems, selectedItems]);

  const handleCreateDeployment = () => {
    if (!providerId) {
      setErrorData({
        title: "No provider selected",
        list: ["Select or create a deployment provider first."],
      });
      return;
    }

    const payload: DeploymentCreatePayload = {
      spec: {
        name: deploymentName.trim(),
        description: deploymentDescription.trim(),
        type: deploymentType === "MCP" ? "mcp" : "agent",
      },
    };

    if (attachTab === "Snapshots") {
      const selectedSnapshotIds = attachSnapshotItems
        .filter((item) => selectedItems.has(item.id))
        .map((item) => item.id);
      if (selectedSnapshotIds.length > 0) {
        payload.snapshot = {
          artifact_type: "flow",
          reference_ids: selectedSnapshotIds,
        };
      }
    } else {
      const selectedRawFlows = flows
        .filter((flow) => selectedItems.has(flow.id))
        .map(buildRawFlowPayload)
        .filter((flowPayload): flowPayload is Record<string, unknown> =>
          Boolean(flowPayload),
        );
      if (selectedRawFlows.length > 0) {
        payload.snapshot = {
          artifact_type: "flow",
          raw_payloads: selectedRawFlows,
        };
      }
    }

    if (configMode === "reuse") {
      const selectedConfig = deploymentConfigs.find(
        (config) => config.id === configName || config.name === configName,
      );
      if (selectedConfig) {
        payload.config = { reference_id: selectedConfig.id };
      }
    } else if (configName.trim()) {
      const environmentVariables = envVars.reduce<
        Record<string, { source: "raw"; value: string }>
      >((acc, item) => {
        const key = item.key.trim();
        if (!key) {
          return acc;
        }
        return {
          ...acc,
          [key]: {
            source: "raw",
            value: item.value,
          },
        };
      }, {});

      payload.config = {
        raw_payload: {
          name: configName.trim(),
          description: deploymentDescription.trim(),
          environment_variables: environmentVariables,
        },
      };
    }

    createDeploymentMutation.mutate(payload, {
      onSuccess: async () => {
        await Promise.all([
          deploymentsQuery.refetch(),
          configsQuery.refetch(),
          snapshotsQuery.refetch(),
        ]);
        handleSubmit();
      },
      onError: () => {
        setErrorData({
          title: "Could not create deployment",
          list: ["Please review provider credentials and deployment payload."],
        });
      },
    });
  };

  return (
    <div className="flex h-full flex-col p-5">
      {!providersQuery.isLoading && !hasProviders ? (
        <div className="flex h-full flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border bg-muted/20">
          <div className="max-w-lg text-center">
            <h3 className="text-lg font-semibold">No deployment providers</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Register a deployment provider to start creating and managing
              deployments in this project.
            </p>
          </div>
          <Button onClick={() => setRegisterProviderOpen(true)}>
            Register Deployment Provider
          </Button>
        </div>
      ) : (
        <>
      <div className="flex justify-between items-center">
        <div className="relative flex h-9 items-center rounded-lg border border-border bg-background p-1">
          <div
            className="absolute h-7 rounded-md bg-muted shadow-sm transition-all duration-200"
            style={{
              width: activeView === "Live Deployments" ? 133 : 175,
              left: activeView === "Live Deployments" ? "4px" : 141,
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
          disabled={!providerId && activeView === "Live Deployments"}
          onClick={() => {
            if (activeView === "Deployment Providers") {
              setRegisterProviderOpen(true);
            } else {
              handleOpenChange(true);
            }
          }}
        >
          <ForwardedIconComponent name="Plus" />{" "}
          {activeView === "Deployment Providers"
            ? "Add Provider"
            : "New Deployment"}
        </Button>
      </div>

      {activeView === "Deployment Providers" && (
        <div className="pt-4">
          <DeploymentProvidersView
            providers={providers}
            configurations={deploymentConfigs}
            selectedProviderId={providerId || null}
            onSelectProvider={setSelectedProviderId}
            onConfigureProvider={handleConfigureProvider}
            selectedProviderDeploymentCount={liveDeployments.length}
            isLoadingProviders={providersQuery.isLoading}
            isLoadingConfigurations={configsQuery.isLoading}
          />
        </div>
      )}

      {activeView === "Live Deployments" && (
        <div className="flex h-full flex-col pt-4">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted-foreground">Provider Account:</span>
            <Select
              value={providerId || undefined}
              onValueChange={setSelectedProviderId}
              disabled={providers.length === 0}
            >
              <SelectTrigger
                className="h-8 min-w-[250px] max-w-full flex-1 bg-background text-foreground sm:w-[360px] sm:flex-none"
                title={selectedProviderLabel}
              >
                <span className="flex min-w-0 items-center gap-2">
                  {selectedProvider && (
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-zinc-700">
                      <ProviderOptionIcon provider={selectedProvider} />
                    </span>
                  )}
                  <span className="truncate text-left">{selectedProviderLabel}</span>
                </span>
              </SelectTrigger>
              <SelectContent>
                {providers.map((provider) => (
                  <SelectItem key={provider.id} value={provider.id}>
                    <div className="flex items-center gap-2">
                      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-zinc-700">
                        <ProviderOptionIcon provider={provider} />
                      </div>
                      <span className="truncate">{getProviderAccountLabel(provider)}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="relative h-full">
            {deploymentsQuery.isLoading ? (
              <DeploymentsTableSkeleton />
            ) : (
              <TableComponent
                rowHeight={65}
                cellSelection={false}
                tableOptions={{ hide_options: true }}
                columnDefs={columnDefs}
                rowData={deploymentRows}
                className="w-full ag-no-border"
                pagination
                quickFilterText=""
                gridOptions={{
                  ensureDomOrder: true,
                  colResizeDefault: "shift",
                }}
              />
            )}
            {!deploymentsQuery.isLoading && deploymentRows.length === 0 && (
              <div className="px-1 pt-3 text-sm text-muted-foreground">
                No deployments found for the selected provider.
              </div>
            )}
          </div>
        </div>
      )}
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
        height="h-[700px]"
        size="medium-h-full"
        footer={
          <StepperModalFooter
            currentStep={currentStep}
            totalSteps={TOTAL_STEPS}
            onBack={handleBack}
            onNext={handleNext}
            onSubmit={handleCreateDeployment}
            nextDisabled={
              (currentStep === 1 && !deploymentName.trim()) ||
              (currentStep === 2 && selectedItems.size === 0) ||
              (currentStep === 3 && !configName.trim())
            }
            submitLabel="Deployment"
          />
        }
      >
        {currentStep === 1 && (
          <StepBasics
            deploymentName={deploymentName}
            setDeploymentName={setDeploymentName}
            deploymentDescription={deploymentDescription}
            setDeploymentDescription={setDeploymentDescription}
            deploymentType={deploymentType}
            setDeploymentType={setDeploymentType}
          />
        )}

        {currentStep === 2 && (
          <StepAttach
            attachTab={attachTab}
            setAttachTab={setAttachTab}
            selectedItems={selectedItems}
            toggleItem={toggleItem}
            flows={attachFlowItems}
            snapshots={attachSnapshotItems}
          />
        )}

        {currentStep === 3 && (
          <StepConfiguration
            configMode={configMode}
            setConfigMode={setConfigMode}
            configName={configName}
            setConfigName={setConfigName}
            keyFormat={keyFormat}
            setKeyFormat={setKeyFormat}
            envVars={envVars}
            setEnvVars={setEnvVars}
          />
        )}
        {currentStep === 4 && (
          <StepScope
            variableScope={variableScope}
            setVariableScope={setVariableScope}
          />
        )}
        {currentStep === 5 && (
          <StepReview
            deploymentType={deploymentType}
            deploymentName={deploymentName}
            deploymentDescription={deploymentDescription}
            selectedItems={selectedReviewItems}
            configMode={configMode}
            configName={configName}
            keyFormat={keyFormat}
            envVars={envVars}
            variableScope={variableScope}
          />
        )}
      </StepperModal>
      </>
      )}
      <RegisterDeploymentProviderModal
        open={registerProviderOpen}
        onOpenChange={setRegisterProviderOpen}
      />
      <ConfigureDeploymentProviderModal
        open={configureProviderOpen}
        provider={providerToConfigure}
        onOpenChange={(nextOpen) => {
          setConfigureProviderOpen(nextOpen);
          if (!nextOpen) {
            setProviderToConfigure(null);
          }
        }}
      />
    </div>
  );
};

export default DeploymentsTab;
