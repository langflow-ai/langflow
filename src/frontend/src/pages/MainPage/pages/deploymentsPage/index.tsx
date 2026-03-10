import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { getURL } from "@/controllers/API/helpers/constants";
import {
  type DeploymentCreatePayload,
  type DeploymentCreateResponse,
  type DeploymentListItem,
  type DeploymentProvider,
  useGetDeploymentById,
  useGetDeploymentProviders,
  useGetDeployments,
  usePostCreateDeployment,
  usePostDetectDeploymentEnvVars,
} from "@/controllers/API/queries/deployments/use-deployments";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import StepperModal, {
  StepperModalFooter,
} from "@/modals/stepperModal/StepperModal";
import useAlertStore from "@/stores/alertStore";
import { useFolderStore } from "@/stores/foldersStore";
import type { FlowType } from "@/types/flow";
import type { FlowHistoryEntry } from "@/types/flow/history";
import { ConfigureDeploymentProviderModal } from "./components/ConfigureDeploymentProviderModal";
import { DeploymentCreationStatusView } from "./components/DeploymentCreationStatusView";
import type { DeploymentListRow } from "./components/DeploymentProvidersView";
import { DeploymentsEmptyState } from "./components/DeploymentsEmptyState";
import { DeploymentsLoadingView } from "./components/DeploymentsLoadingView";
import { DeploymentsView } from "./components/DeploymentsView";
import { RegisterDeploymentProviderModal } from "./components/RegisterDeploymentProviderModal";
import { StepAttach } from "./components/steps/StepAttach";
import { StepBasics } from "./components/steps/StepBasics";
import { StepConfiguration } from "./components/steps/StepConfiguration";
import { StepReview } from "./components/steps/StepReview";
import { TestAgentModal } from "./components/TestAgentModal";
import { type EnvVar, TOTAL_STEPS } from "./constants";
import { useDeploymentForm } from "./hooks/useDeploymentForm";
import type {
  CreatedDeploymentUiMeta,
  DeploymentCreationState,
  FlowCheckpointGroup,
  TestDeploymentTarget,
} from "./types";
import {
  fetchFlowHistoryWithDedupe,
  formatDateLabel,
  mapProviderModeToLabel,
  validateEnvVars,
} from "./utils";

const STEP_LABELS = [
  "Basics",
  "Attach Flows/Snapshots",
  "Config",
  "Variable Scope",
  "Review",
];

const DeploymentsTab = () => {
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(
    null,
  );
  const [registerProviderOpen, setRegisterProviderOpen] = useState(false);
  const [configureProviderOpen, setConfigureProviderOpen] = useState(false);
  const [deploymentsPage, setDeploymentsPage] = useState(1);
  const [deploymentsPageSize] = useState(20);
  const [creationState, setCreationState] =
    useState<DeploymentCreationState>("idle");
  const [createdDeploymentName, setCreatedDeploymentName] = useState("");
  const [createdDeploymentType, setCreatedDeploymentType] = useState<
    "agent" | "mcp" | null
  >(null);
  const [createdDeploymentId, setCreatedDeploymentId] = useState("");
  const [createdDeploymentItem, setCreatedDeploymentItem] =
    useState<DeploymentListItem | null>(null);
  const [createdDeploymentUiMeta, setCreatedDeploymentUiMeta] =
    useState<CreatedDeploymentUiMeta | null>(null);
  const [testAgentModalOpen, setTestAgentModalOpen] = useState(false);
  const [testDeploymentTarget, setTestDeploymentTarget] =
    useState<TestDeploymentTarget | null>(null);
  const [providerToConfigure, setProviderToConfigure] =
    useState<DeploymentProvider | null>(null);
  const [checkpointGroups, setCheckpointGroups] = useState<
    FlowCheckpointGroup[]
  >([]);
  const [activeSubTab, setActiveSubTab] = useState<"deployments" | "providers">(
    "deployments",
  );

  const providersQuery = useGetDeploymentProviders({
    refetchOnWindowFocus: false,
  });
  const providers = providersQuery.data?.providers || [];
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
    { providerId, page: deploymentsPage, pageSize: deploymentsPageSize },
    {
      enabled: Boolean(providerId),
      refetchOnWindowFocus: false,
    },
  );
  const currentProjectId = folderId ?? myCollectionId ?? undefined;
  const flowsQuery = useGetRefreshFlowsQuery(
    {
      get_all: false,
      folder_id: currentProjectId,
      remove_example_flows: true,
      page: 1,
      size: 15,
    },
    {
      refetchOnWindowFocus: false,
      enabled: Boolean(currentProjectId),
    },
  );
  const createDeploymentMutation = usePostCreateDeployment();
  const getDeploymentByIdMutation = useGetDeploymentById();
  const { mutateAsync: detectDeploymentEnvVars } =
    usePostDetectDeploymentEnvVars();
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

  const liveDeployments = useMemo(() => {
    const deployments = deploymentsQuery.data?.deployments || [];
    if (!createdDeploymentItem) {
      return deployments;
    }

    const deploymentsWithoutCreated = deployments.filter(
      (deployment) => deployment.id !== createdDeploymentItem.id,
    );
    return [createdDeploymentItem, ...deploymentsWithoutCreated];
  }, [deploymentsQuery.data?.deployments, createdDeploymentItem]);
  const flows = useMemo<FlowType[]>(() => {
    const data = flowsQuery.data;
    if (!data) {
      return [];
    }
    return Array.isArray(data) ? data : data.items;
  }, [flowsQuery.data]);

  const deploymentRows = useMemo<DeploymentListRow[]>(() => {
    return liveDeployments.map((deployment) => {
      const providerDeploymentId =
        typeof deployment.resource_key === "string" &&
        deployment.resource_key.trim().length > 0
          ? deployment.resource_key
          : deployment.id;
      const deploymentRowId = deployment.id;
      const createdMeta =
        createdDeploymentUiMeta?.deploymentId === deploymentRowId
          ? createdDeploymentUiMeta
          : null;
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
        id: deploymentRowId,
        name: deployment.name,
        url: `Deployment ID: ${providerDeploymentId}`,
        type: deployment.type.toUpperCase() === "MCP" ? "MCP" : "Agent",
        deploymentType:
          deployment.type.toUpperCase() === "MCP" ? "mcp" : "agent",
        mode: mapProviderModeToLabel(mode),
        attached:
          deployment.attached_count ??
          createdMeta?.attachedCount ??
          snapshotIds.length ??
          0,
        modifiedDate: formatDateLabel(
          deployment.updated_at ??
            deployment.created_at ??
            createdMeta?.createdAt ??
            null,
        ),
        createdDate: formatDateLabel(
          deployment.created_at ??
            deployment.updated_at ??
            createdMeta?.createdAt ??
            null,
        ),
      };
    });
  }, [createdDeploymentUiMeta, liveDeployments]);

  useEffect(() => {
    let cancelled = false;
    const loadCheckpoints = async () => {
      if (!newDeploymentOpen || flows.length === 0) {
        setCheckpointGroups([]);
        return;
      }
      const responses = await Promise.all(
        flows.map(async (flow) => {
          try {
            const response = await fetchFlowHistoryWithDedupe(
              `${getURL("FLOWS")}/${flow.id}/history/?limit=20&offset=0`,
            );
            return { flow, entries: response.entries ?? [] };
          } catch {
            return { flow, entries: [] as FlowHistoryEntry[] };
          }
        }),
      );
      const groups = responses.map(({ flow, entries }) => ({
        flowId: flow.id,
        flowName: flow.name,
        checkpoints: entries.map((entry) => ({
          id: entry.id,
          name: entry.version_tag
            ? `Version ${entry.version_tag}`
            : "Checkpoint",
          updatedDate: formatDateLabel(entry.created_at),
        })),
      }));
      if (!cancelled) {
        setCheckpointGroups(groups);
      }
    };
    loadCheckpoints();
    return () => {
      cancelled = true;
    };
  }, [flows, newDeploymentOpen]);

  const [detectedEnvVars, setDetectedEnvVars] = useState<EnvVar[]>([]);

  const prevSelectedKeyRef = useRef("");

  useEffect(() => {
    if (!newDeploymentOpen) {
      prevSelectedKeyRef.current = "";
      setDetectedEnvVars([]);
    }
  }, [newDeploymentOpen]);

  useEffect(() => {
    setCreatedDeploymentItem(null);
    setCreatedDeploymentUiMeta(null);
    setDeploymentsPage(1);
  }, [providerId]);

  useEffect(() => {
    if (!newDeploymentOpen || selectedItems.size === 0) {
      setDetectedEnvVars([]);
      return;
    }

    let cancelled = false;
    const checkpointIds = Array.from(selectedItems);
    const detect = async () => {
      try {
        const response = await detectDeploymentEnvVars({
          reference_ids: checkpointIds,
        });
        if (!cancelled) {
          setDetectedEnvVars(
            (response.variables || []).map((item) => ({
              key: item.global_variable_name ?? item.key,
              value: item.global_variable_name ?? "",
              globalVar: Boolean(item.global_variable_name),
              deploymentKey: item.key,
            })),
          );
        }
      } catch {
        if (!cancelled) {
          setDetectedEnvVars([]);
        }
      }
    };
    void detect();
    return () => {
      cancelled = true;
    };
  }, [newDeploymentOpen, selectedItems, detectDeploymentEnvVars]);

  useEffect(() => {
    if (!newDeploymentOpen || currentStep < 3) {
      return;
    }
    if (envVars.length > 0 || detectedEnvVars.length === 0) {
      return;
    }
    setEnvVars(detectedEnvVars);
  }, [
    currentStep,
    detectedEnvVars,
    envVars.length,
    newDeploymentOpen,
    setEnvVars,
  ]);

  const selectedReviewItems = useMemo(() => {
    return checkpointGroups
      .flatMap((group) =>
        group.checkpoints.map((checkpoint) => ({
          id: checkpoint.id,
          name: `${group.flowName} (${checkpoint.name})`,
        })),
      )
      .filter((item) => selectedItems.has(item.id))
      .map((item) => ({ name: item.name }));
  }, [checkpointGroups, selectedItems]);

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

    const selectedCheckpointIds = Array.from(selectedItems);
    const selectedFlowCount = selectedCheckpointIds.length;
    const requestedAt = new Date().toISOString();

    const trimmedDeploymentName = deploymentName.trim();
    const trimmedDescription = deploymentDescription.trim();

    const payload: DeploymentCreatePayload = {
      provider_id: providerId,
      spec: {
        name: trimmedDeploymentName,
        description: trimmedDescription,
        type: deploymentType === "MCP" ? "mcp" : "agent",
      },
    };

    if (selectedCheckpointIds.length > 0) {
      payload.flow_versions = {
        ids: selectedCheckpointIds,
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
    setCreatedDeploymentUiMeta(null);
    handleSubmit();

    createDeploymentMutation.mutate(payload, {
      onSuccess: async (response: DeploymentCreateResponse) => {
        setCreatedDeploymentId(response.id);
        const resultSnapshotIds = Array.isArray(response.snapshot_ids)
          ? response.snapshot_ids.filter(
              (id): id is string =>
                typeof id === "string" && id.trim().length > 0,
            )
          : [];
        setCreatedDeploymentUiMeta({
          deploymentId: response.id,
          attachedCount: resultSnapshotIds.length || selectedFlowCount,
          createdAt: requestedAt,
        });
        const deployment = await getDeploymentByIdMutation.mutateAsync({
          deploymentId: response.id,
        });
        setCreatedDeploymentItem(deployment);
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
    <div className="relative h-full">
      <div
        className="pointer-events-none absolute inset-0 z-40"
        style={{
          background:
            "linear-gradient(to bottom, transparent 0%, transparent 25%, hsl(var(--background) / 0.5) 45%, hsl(var(--background)) 65%, hsl(var(--background)) 100%)",
        }}
      />
      <div className="flex h-full flex-col pt-5 px-5 3xl:container">
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
                    deploymentRows.find((row) => row.id === createdDeploymentId)
                      ?.mode || undefined,
                });
                setTestAgentModalOpen(true);
                return;
              }
              setNoticeData({
                title: "MCP deployment testing UI will be added soon.",
              });
            }}
          />
        ) : (
          <>
            {/* Sub-tab toggle — always visible */}
            <div className="flex items-center justify-between gap-4">
              <div className="inline-flex items-center rounded-md border border-border bg-background p-1">
                <button
                  type="button"
                  onClick={() => setActiveSubTab("deployments")}
                  className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                    activeSubTab === "deployments"
                      ? "bg-muted text-primary shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Deployments
                </button>
                <button
                  type="button"
                  onClick={() => setActiveSubTab("providers")}
                  className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                    activeSubTab === "providers"
                      ? "bg-muted text-primary shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Deployment Providers
                </button>
              </div>
            </div>

            {/* Content area */}
            {providersQuery.isLoading ? (
              <DeploymentsLoadingView activeSubTab={activeSubTab} />
            ) : !hasProviders ? (
              <DeploymentsEmptyState
                activeSubTab={activeSubTab}
                onCreateDeployment={() => handleOpenChange(true)}
                onAddProvider={() => setRegisterProviderOpen(true)}
              />
            ) : (
              <DeploymentsView
                providers={providers}
                deploymentRows={deploymentRows}
                selectedProviderId={providerId || null}
                onSelectProvider={setSelectedProviderId}
                onConfigureProvider={handleConfigureProvider}
                selectedProviderDeploymentCount={liveDeployments.length}
                isLoadingDeployments={deploymentsQuery.isLoading}
                isLoadingProviders={providersQuery.isLoading}
                page={deploymentsPage}
                pageSize={deploymentsPageSize}
                total={deploymentsQuery.data?.total ?? 0}
                onPageChange={setDeploymentsPage}
                onCreateDeployment={() => handleOpenChange(true)}
                activeSubTab={activeSubTab}
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
            )}
            <StepperModal
              open={newDeploymentOpen}
              onOpenChange={handleOpenChange}
              currentStep={currentStep}
              totalSteps={TOTAL_STEPS}
              title="Create Deployment"
              bgClassName="bg-secondary"
              icon="Rocket"
              description="Deploy your Langflow workflows to watsonx Orchestrate"
              contentClassName="bg-background"
              stepLabels={STEP_LABELS}
              onBack={() => handleOpenChange(false)}
              backLabel="Back to Deployments"
              footer={
                <StepperModalFooter
                  currentStep={currentStep}
                  totalSteps={TOTAL_STEPS}
                  onBack={handleBack}
                  onNext={() => {
                    if (currentStep === 2) {
                      const selKey = Array.from(selectedItems).sort().join(",");
                      const selectionChanged =
                        selKey !== prevSelectedKeyRef.current;
                      const shouldSeedDetectedVars =
                        selectionChanged ||
                        (envVars.length === 0 && detectedEnvVars.length > 0);

                      if (shouldSeedDetectedVars) {
                        prevSelectedKeyRef.current = selKey;
                        setEnvVars(detectedEnvVars);
                      }
                    }
                    if (currentStep === 3) {
                      const envVarValidationErrors = validateEnvVars(envVars);
                      if (envVarValidationErrors.length > 0) {
                        setErrorData({
                          title: "Invalid environment variables",
                          list: envVarValidationErrors,
                        });
                        return;
                      }
                    }
                    handleNext();
                  }}
                  onSubmit={handleCreateDeployment}
                  nextDisabled={
                    (currentStep === 1 && !deploymentName.trim()) ||
                    (currentStep === 2 && selectedItems.size === 0) ||
                    (currentStep === 3 && validateEnvVars(envVars).length > 0)
                  }
                  submitLabel="Deploy"
                  onCancel={() => handleOpenChange(false)}
                  nextLabel="Continue"
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
                  flows={checkpointGroups}
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
    </div>
  );
};

export default DeploymentsTab;
