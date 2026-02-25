import { useEffect, useMemo, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  type DeploymentCreatePayload,
  type DeploymentProvider,
  type DeploymentCreateResponse,
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
import { type EnvVar, TOTAL_STEPS } from "./constants";
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
import { DeploymentCreationStatusView } from "./DeploymentCreationStatusView";
import { TestAgentModal } from "./TestAgentModal";
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
  if (!flow.data || !flow.folder_id) {
    return null;
  }

  return {
    id: flow.id,
    name: flow.name,
    description: flow.description || "",
    data: flow.data,
    tags: flow.tags || [],
    provider_data: {
      project_id: flow.folder_id,
    },
  };
};

/**
 * Walk every node in the given flows and collect field names that
 * reference global / environment variables (`load_from_db === true`).
 */
const extractEnvVarsFromFlows = (flows: FlowType[]): EnvVar[] => {
  const seen = new Set<string>();

  for (const flow of flows) {
    if (!flow.data?.nodes) continue;
    for (const node of flow.data.nodes) {
      const template =
        node.type === "genericNode"
          ? (node.data as Record<string, any>)?.node?.template
          : undefined;
      if (!template) continue;
      for (const fieldName of Object.keys(template)) {
        const field = template[fieldName];
        if (
          field?.load_from_db &&
          typeof field.value === "string" &&
          field.value
        ) {
          seen.add(field.value);
        }
      }
    }
  }

  return Array.from(seen)
    .sort()
    .map((key) => ({ key, value: key, globalVar: true }));
};

const validateEnvVars = (envVars: EnvVar[]): string[] => {
  const errors: string[] = [];
  const seenKeys = new Set<string>();

  envVars.forEach((item, index) => {
    const row = index + 1;
    const key = item.key.trim();
    const value = item.value.trim();

    if (!key && !value) {
      return;
    }

    if (!key) {
      errors.push(`Row ${row}: key is required when a value is provided.`);
      return;
    }

    if (!value) {
      errors.push(`Row ${row}: value is required for key "${key}".`);
      return;
    }

    if (seenKeys.has(key)) {
      errors.push(`Row ${row}: duplicate key "${key}". Keys must be unique.`);
      return;
    }
    seenKeys.add(key);
  });

  return errors;
};

type DeploymentCreationState = "idle" | "creating" | "success" | "error";
type TestDeploymentTarget = {
  id: string;
  name: string;
  deploymentType: "agent" | "mcp";
  mode?: string;
};

const DeploymentsTab = () => {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(
    null,
  );
  const [registerProviderOpen, setRegisterProviderOpen] = useState(false);
  const [configureProviderOpen, setConfigureProviderOpen] = useState(false);
  const [providerListMode, setProviderListMode] =
    useState<ProviderListMode>("deployments");
  const [creationState, setCreationState] =
    useState<DeploymentCreationState>("idle");
  const [createdDeploymentName, setCreatedDeploymentName] = useState("");
  const [createdDeploymentType, setCreatedDeploymentType] = useState<
    "agent" | "mcp" | null
  >(null);
  const [createdDeploymentId, setCreatedDeploymentId] = useState("");
  const [testAgentModalOpen, setTestAgentModalOpen] = useState(false);
  const [testDeploymentTarget, setTestDeploymentTarget] =
    useState<TestDeploymentTarget | null>(null);
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
  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === providerId) || null,
    [providers, providerId],
  );

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
    { get_all: true, remove_example_flows: true },
    {
      refetchOnWindowFocus: false,
      enabled: true,
    },
  );
  const createDeploymentMutation = usePostCreateDeployment({ providerId });

  const liveDeployments = deploymentsQuery.data?.deployments || [];
  const deploymentConfigs = configsQuery.data?.configs || [];
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
        id: deployment.id,
        name: deployment.name,
        url: `Deployment ID: ${deployment.id}`,
        type: deployment.type.toUpperCase() === "MCP" ? "MCP" : "Agent",
        deploymentType:
          deployment.type.toUpperCase() === "MCP" ? "mcp" : "agent",
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
      })),
    [flows],
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
    envVars,
    setEnvVars,
    handleBack,
    handleNext,
    handleSubmit,
    handleOpenChange,
    toggleItem,
  } = useDeploymentForm();

  const selectedFlowObjects = useMemo(
    () => flows.filter((f) => selectedItems.has(f.id)),
    [flows, selectedItems],
  );

  const detectedEnvVars = useMemo(
    () => extractEnvVarsFromFlows(selectedFlowObjects),
    [selectedFlowObjects],
  );

  const prevSelectedKeyRef = useRef("");

  useEffect(() => {
    if (!newDeploymentOpen) {
      prevSelectedKeyRef.current = "";
    }
  }, [newDeploymentOpen]);

  const selectedReviewItems = useMemo(() => {
    return attachFlowItems
      .filter((item) => selectedItems.has(item.id))
      .map((item) => ({ name: item.name }));
  }, [attachFlowItems, selectedItems]);

  const handleCreateDeployment = () => {
    if (!providerId) {
      setErrorData({
        title: "No provider selected",
        list: ["Select or create a deployment provider first."],
      });
      return;
    }

    const envVarValidationErrors = validateEnvVars(envVars);
    if (envVarValidationErrors.length > 0) {
      setErrorData({
        title: "Invalid environment variables",
        list: envVarValidationErrors,
      });
      return;
    }

    const selectedFlows = flows.filter((flow) => selectedItems.has(flow.id));
    const invalidProjectFlows = selectedFlows
      .filter((flow) => !flow.folder_id?.trim())
      .map((flow) => flow.name || flow.id);
    if (invalidProjectFlows.length > 0) {
      setErrorData({
        title: "Missing flow project metadata",
        list: [
          "Each selected flow must belong to a project before deployment.",
          `Missing project_id for: ${invalidProjectFlows.join(", ")}`,
        ],
      });
      return;
    }

    const trimmedDeploymentName = deploymentName.trim();
    const trimmedDescription = deploymentDescription.trim();

    const payload: DeploymentCreatePayload = {
      spec: {
        name: trimmedDeploymentName,
        description: trimmedDescription,
        type: deploymentType === "MCP" ? "mcp" : "agent",
      },
    };

    const selectedRawFlows = selectedFlows
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

    const environmentVariables = envVars.reduce<
      Record<string, { source: "raw" | "variable"; value: string }>
    >((acc, item) => {
      const key = item.key.trim();
      const value = item.value.trim();
      if (!key || !value) {
        return acc;
      }
      return {
        ...acc,
        [key]: {
          source: item.globalVar ? "variable" : "raw",
          value,
        },
      };
    }, {});

    if (Object.keys(environmentVariables).length > 0) {
      payload.config = {
        raw_payload: {
          name: trimmedDeploymentName,
          description: trimmedDescription,
          environment_variables: environmentVariables,
        },
      };
    }

    setCreationState("creating");
    setCreatedDeploymentId("");
    setCreatedDeploymentName(trimmedDeploymentName);
    setCreatedDeploymentType(payload.spec.type);
    handleSubmit();

    createDeploymentMutation.mutate(payload, {
      onSuccess: async (response: DeploymentCreateResponse) => {
        setCreatedDeploymentId(response.id);
        await Promise.all([
          deploymentsQuery.refetch(),
          configsQuery.refetch(),
          snapshotsQuery.refetch(),
        ]);
        setCreationState("success");
      },
      onError: () => {
        setCreationState("error");
        setErrorData({
          title: "Could not create deployment",
          list: ["Please review provider credentials and deployment payload."],
        });
      },
    });
  };

  return (
    <div className="flex h-full flex-col p-5">
      {creationState !== "idle" ? (
        <DeploymentCreationStatusView
          state={creationState}
          deploymentName={createdDeploymentName}
          deploymentType={createdDeploymentType}
          onBack={() => {
            setCreationState("idle");
          }}
          onPrimaryAction={() => {
            if (createdDeploymentType === "agent") {
              if (!createdDeploymentId) {
                setNoticeData({
                  title: "Deployment ID not available yet. Please try again.",
                });
                return;
              }
              setTestDeploymentTarget({
                id: createdDeploymentId,
                name: createdDeploymentName,
                deploymentType: "agent",
                mode:
                  deploymentRows.find((row) => row.id === createdDeploymentId)?.mode ||
                  undefined,
              });
              setTestAgentModalOpen(true);
              return;
            }
            setNoticeData({
              title: "MCP deployment testing UI will be added soon.",
            });
          }}
        />
      ) : !providersQuery.isLoading && !hasProviders ? (
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
              onTestAgent={(deployment) => {
                if (
                  !deployment.id.trim() ||
                  !deployment.name.trim() ||
                  deployment.deploymentType !== "agent"
                ) {
                  return;
                }
                setTestDeploymentTarget(deployment);
                setTestAgentModalOpen(true);
              }}
            />
          </div>
          <StepperModal
            open={newDeploymentOpen}
            onOpenChange={handleOpenChange}
            currentStep={currentStep}
            totalSteps={TOTAL_STEPS}
            title="Create Deployment"
            icon="Rocket"
            description="Deploy your Langflow workflows to watsonx Orchestrate"
            stepLabels={["Basics", "Attach", "Configuration", "Review"]}
            width="w-[800px]"
            height="h-[700px]"
            size="medium-h-full"
            footer={
              <StepperModalFooter
                currentStep={currentStep}
                totalSteps={TOTAL_STEPS}
                onBack={handleBack}
                onNext={() => {
                  if (currentStep === 2) {
                    const selKey = Array.from(selectedItems)
                      .sort()
                      .join(",");
                    const selectionChanged = selKey !== prevSelectedKeyRef.current;
                    const shouldSeedDetectedVars =
                      selectionChanged ||
                      (envVars.length === 0 && detectedEnvVars.length > 0);

                    if (shouldSeedDetectedVars) {
                      prevSelectedKeyRef.current = selKey;
                      setEnvVars(detectedEnvVars);
                    }
                  }
                  handleNext();
                }}
                onSubmit={handleCreateDeployment}
                nextDisabled={
                  (currentStep === 1 && !deploymentName.trim()) ||
                  (currentStep === 2 && selectedItems.size === 0)
                }
                submitLabel="Deploy"
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
                selectedItems={selectedItems}
                toggleItem={toggleItem}
                flows={attachFlowItems}
              />
            )}

            {currentStep === 3 && (
              <StepConfiguration
                envVars={envVars}
                setEnvVars={setEnvVars}
                detectedVarCount={detectedEnvVars.length}
              />
            )}
            {currentStep === 4 && (
              <StepReview
                deploymentType={deploymentType}
                deploymentName={deploymentName}
                deploymentDescription={deploymentDescription}
                selectedItems={selectedReviewItems}
                envVars={envVars}
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
      <TestAgentModal
        open={testAgentModalOpen}
        providerId={providerId}
        providerKey={selectedProvider?.provider_key}
        deploymentId={testDeploymentTarget?.id ?? ""}
        deploymentType={testDeploymentTarget?.deploymentType ?? "agent"}
        deploymentMode={testDeploymentTarget?.mode ?? null}
        deploymentName={testDeploymentTarget?.name ?? createdDeploymentName}
        onOpenChange={(nextOpen) => {
          setTestAgentModalOpen(nextOpen);
          if (!nextOpen) {
            setTestDeploymentTarget(null);
          }
        }}
      />
    </div>
  );
};

export default DeploymentsTab;
