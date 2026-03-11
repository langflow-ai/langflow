import { useGetDeployments } from "@/controllers/API/queries/deployments/use-deployments";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import useAlertStore from "@/stores/alertStore";
import { useFolderStore } from "@/stores/foldersStore";
import type { FlowType } from "@/types/flow";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { ConfigureDeploymentProviderModal } from "./components/ConfigureDeploymentProviderModal";
import { DeploymentCreationStatusView } from "./components/DeploymentCreationStatusView";
import { DeploymentStepperModal } from "./components/DeploymentStepperModal";
import { DeploymentsEmptyState } from "./components/DeploymentsEmptyState";
import { DeploymentsLoadingView } from "./components/DeploymentsLoadingView";
import { DeploymentsView } from "./components/DeploymentsView";
import { RegisterDeploymentProviderModal } from "./components/RegisterDeploymentProviderModal";
import { SubTabToggle } from "./components/SubTabToggle";
import { TestAgentModal } from "./components/TestAgentModal";
import { useCheckpoints } from "./hooks/useCheckpoints";
import { useDeploymentCreation } from "./hooks/useDeploymentCreation";
import { useDeploymentForm } from "./hooks/useDeploymentForm";
import { useDeploymentRows } from "./hooks/useDeploymentRows";
import { useProviders } from "./hooks/useProviders";
import type { TestDeploymentTarget } from "./types";

const DeploymentsTab = () => {
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);

  const [deploymentsPage, setDeploymentsPage] = useState(1);
  const [deploymentsPageSize] = useState(20);
  const [testAgentModalOpen, setTestAgentModalOpen] = useState(false);
  const [testDeploymentTarget, setTestDeploymentTarget] =
    useState<TestDeploymentTarget | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<"deployments" | "providers">(
    "deployments",
  );

  // --- Providers ---
  const {
    providers,
    providerId,
    selectedProvider,
    setSelectedProviderId,
    hasProviders,
    providersQuery,
    registerProviderOpen,
    setRegisterProviderOpen,
    configureProviderOpen,
    setConfigureProviderOpen,
    providerToConfigure,
    setProviderToConfigure,
    handleConfigureProvider,
  } = useProviders();

  // --- Deployment form ---
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

  // --- Deployment creation ---
  const {
    creationState,
    setCreationState,
    createdDeploymentName,
    createdDeploymentType,
    createdDeploymentId,
    createdDeploymentItem,
    createdDeploymentUiMeta,
    resetCreatedState,
    handleCreateDeployment,
  } = useDeploymentCreation();

  // --- Queries ---
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
  const flows = useMemo<FlowType[]>(() => {
    const data = flowsQuery.data;
    if (!data) {
      return [];
    }
    return Array.isArray(data) ? data : data.items;
  }, [flowsQuery.data]);

  // --- Checkpoints & env var detection ---
  const { checkpointGroups, detectedEnvVars } = useCheckpoints({
    flows,
    newDeploymentOpen,
    selectedItems,
    currentStep,
    envVars,
    setEnvVars,
  });

  // --- Deployment rows ---
  const { liveDeployments, deploymentRows } = useDeploymentRows({
    deployments: deploymentsQuery.data?.deployments || [],
    createdDeploymentItem,
    createdDeploymentUiMeta,
  });

  // Reset created state on provider change
  useEffect(() => {
    resetCreatedState();
    setDeploymentsPage(1);
  }, [providerId, resetCreatedState]);

  // --- Review items ---
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

  // --- Create handler ---
  const onCreateDeployment = () => {
    handleCreateDeployment({
      providerId,
      deploymentName,
      deploymentDescription,
      deploymentType,
      selectedItems,
      envVars,
      onSubmit: handleSubmit,
    });
  };

  // --- Primary action from creation status ---
  const onCreationPrimaryAction = () => {
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
  };

  return (
    <div className="relative h-full">
      <div
        className="pointer-events-none absolute inset-0 z-40"
        style={{
          background:
            (providersQuery.isLoading || !hasProviders) && false
              ? "linear-gradient(to bottom, transparent 0%, transparent 25%, hsl(var(--background) / 0.5) 45%, hsl(var(--background)) 65%, hsl(var(--background)) 100%)"
              : "transparent",
        }}
      />
      <div className="flex h-full flex-col pt-5 px-5 3xl:container">
        {creationState !== "idle" ? (
          <DeploymentCreationStatusView
            state={creationState}
            deploymentName={createdDeploymentName}
            deploymentType={createdDeploymentType}
            onBack={() => setCreationState("idle")}
            onPrimaryAction={onCreationPrimaryAction}
          />
        ) : (
          <>
            <SubTabToggle
              activeSubTab={activeSubTab}
              onChangeSubTab={setActiveSubTab}
            />

            {providersQuery.isLoading && false ? (
              <DeploymentsLoadingView activeSubTab={activeSubTab} />
            ) : !hasProviders && false ? (
              <DeploymentsEmptyState
                activeSubTab={activeSubTab}
                onCreateDeployment={() => handleOpenChange(true)}
                onAddProvider={() => setRegisterProviderOpen(true)}
              />
            ) : (
              <div className="flex-1 min-h-0">
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
              </div>
            )}
            <DeploymentStepperModal
              open={newDeploymentOpen}
              onOpenChange={handleOpenChange}
              currentStep={currentStep}
              deploymentType={deploymentType}
              setDeploymentType={setDeploymentType}
              deploymentName={deploymentName}
              setDeploymentName={setDeploymentName}
              deploymentDescription={deploymentDescription}
              setDeploymentDescription={setDeploymentDescription}
              selectedItems={selectedItems}
              toggleItem={toggleItem}
              checkpointGroups={checkpointGroups}
              envVars={envVars}
              setEnvVars={setEnvVars}
              detectedVarCount={detectedEnvVars.length}
              selectedReviewItems={selectedReviewItems}
              providerName={selectedProvider?.provider_key}
              onBack={handleBack}
              onNext={handleNext}
              onSubmit={onCreateDeployment}
            />
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
