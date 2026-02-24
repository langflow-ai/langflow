import { useEffect, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  type DeploymentCreatePayload,
  type DeploymentProvider,
  useGetDeploymentConfigs,
  useGetDeploymentProviders,
  useGetDeploymentSnapshots,
  useGetDeployments,
  usePostCreateDeployment,
} from "@/controllers/API/queries/deployments/use-deployments";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { StepperModal, StepperModalFooter } from "@/modals/stepperModal";
import useAlertStore from "@/stores/alertStore";
import type { FlowType } from "@/types/flow";
import { ConfigureDeploymentProviderModal } from "./ConfigureDeploymentProviderModal";
import { TOTAL_STEPS } from "./constants";
import {
  DeploymentProvidersView,
  type DeploymentListRow,
  type ProviderListMode,
} from "./DeploymentProvidersView";
import { RegisterDeploymentProviderModal } from "./RegisterDeploymentProviderModal";
import { StepAttach } from "./steps/StepAttach";
import { StepBasics } from "./steps/StepBasics";
import { StepConfiguration } from "./steps/StepConfiguration";
import { StepReview } from "./steps/StepReview";
import { StepScope } from "./steps/StepScope";
import { useDeploymentForm } from "./useDeploymentForm";

const formatDateLabel = (value?: string | null): string => {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }

  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
};

const mapProviderModeToLabel = (mode?: string): string => {
  if (mode === "both" || mode === "live") {
    return "Live";
  }
  return "Draft";
};

const buildRawFlowPayload = (
  flow: FlowType,
): Record<string, unknown> | null => {
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

const DeploymentsTab = () => {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(
    null,
  );
  const [registerProviderOpen, setRegisterProviderOpen] = useState(false);
  const [configureProviderOpen, setConfigureProviderOpen] = useState(false);
  const [providerListMode, setProviderListMode] =
    useState<ProviderListMode>("deployments");
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

  const deploymentRows = useMemo<DeploymentListRow[]>(() => {
    return liveDeployments.map((deployment) => {
      const snapshotIds =
        deployment.provider_data?.snapshot_ids &&
        Array.isArray(deployment.provider_data.snapshot_ids)
          ? deployment.provider_data.snapshot_ids
          : [];
      const mode =
        typeof deployment.provider_data?.mode === "string"
          ? deployment.provider_data.mode
          : undefined;

      return {
        name: deployment.name,
        url: `Deployment ID: ${deployment.id}`,
        type: deployment.type.toUpperCase() === "MCP" ? "MCP" : "Agent",
        mode: mapProviderModeToLabel(mode),
        attached: snapshotIds.length,
        modifiedDate: formatDateLabel(
          deployment.updated_at ?? deployment.created_at ?? null,
        ),
        createdDate: formatDateLabel(
          deployment.created_at ?? deployment.updated_at ?? null,
        ),
      };
    });
  }, [liveDeployments]);

  const attachFlowItems = useMemo(
    () =>
      flows.map((flow) => ({
        id: flow.id,
        name: flow.name,
        updatedDate: formatDateLabel(
          flow.updated_at || flow.date_created || null,
        ),
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
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="secondary"
              className="flex items-center gap-2 font-semibold"
              onClick={() => setRegisterProviderOpen(true)}
            >
              <ForwardedIconComponent name="Plus" />
              Add Provider
            </Button>
            <Button
              className="flex items-center gap-2 font-semibold"
              disabled={!providerId}
              onClick={() => handleOpenChange(true)}
            >
              <ForwardedIconComponent name="Plus" />
              New Deployment
            </Button>
          </div>

          <div className="pt-4">
            <DeploymentProvidersView
              providers={providers}
              configurations={deploymentConfigs}
              deploymentRows={deploymentRows}
              selectedProviderId={providerId || null}
              onSelectProvider={setSelectedProviderId}
              onConfigureProvider={handleConfigureProvider}
              listMode={providerListMode}
              onListModeChange={setProviderListMode}
              selectedProviderDeploymentCount={liveDeployments.length}
              isLoadingDeployments={deploymentsQuery.isLoading}
              isLoadingProviders={providersQuery.isLoading}
              isLoadingConfigurations={configsQuery.isLoading}
            />
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
