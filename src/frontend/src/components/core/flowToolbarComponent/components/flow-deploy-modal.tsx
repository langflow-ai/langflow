import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  type DeploymentCreatePayload,
  useGetDeploymentProviders,
  usePostCreateDeployment,
  usePostDetectDeploymentEnvVars,
} from "@/controllers/API/queries/deployments/use-deployments";
import {
  useGetFlowHistory,
  usePostCreateSnapshot,
} from "@/controllers/API/queries/flow-history";
import { StepperModal, StepperModalFooter } from "@/modals/stepperModal";
import { CURRENT_DRAFT_ID } from "@/pages/FlowPage/components/flowSidebarComponent/components/FlowHistorySidebar/constants";
import { RegisterDeploymentProviderModal } from "@/pages/MainPage/pages/deploymentsPage/components/RegisterDeploymentProviderModal";
import { StepAttach } from "@/pages/MainPage/pages/deploymentsPage/components/steps/StepAttach";
import { StepBasics } from "@/pages/MainPage/pages/deploymentsPage/components/steps/StepBasics";
import { StepConfiguration } from "@/pages/MainPage/pages/deploymentsPage/components/steps/StepConfiguration";
import { StepReview } from "@/pages/MainPage/pages/deploymentsPage/components/steps/StepReview";
import {
  type EnvVar,
  TOTAL_STEPS,
} from "@/pages/MainPage/pages/deploymentsPage/constants";
import { useDeploymentForm } from "@/pages/MainPage/pages/deploymentsPage/hooks/useDeploymentForm";
import useAlertStore from "@/stores/alertStore";
import useHistoryPreviewStore from "@/stores/historyPreviewStore";
import type { FlowHistoryEntry } from "@/types/flow/history";

type FlowDeployModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  flowId: string;
  flowName: string;
};

const validateEnvVars = (envVars: EnvVar[]): string[] => {
  const errors: string[] = [];
  const seenKeys = new Set<string>();

  envVars.forEach((item, index) => {
    const row = index + 1;
    const key = item.key.trim();
    const value = item.value.trim();

    if (!key && !value) return;
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

export default function FlowDeployModal({
  open,
  onOpenChange,
  flowId,
  flowName,
}: FlowDeployModalProps) {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const previewId = useHistoryPreviewStore((state) => state.previewId);
  const [registerProviderOpen, setRegisterProviderOpen] = useState(false);
  const [detectedEnvVars, setDetectedEnvVars] = useState<EnvVar[]>([]);
  const prevSelectedKeyRef = useRef("");

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
    setSelectedItems,
    envVars,
    setEnvVars,
    handleBack,
    handleNext,
    handleSubmit,
    handleOpenChange,
    toggleItem,
  } = useDeploymentForm();

  useEffect(() => {
    if (open !== newDeploymentOpen) {
      handleOpenChange(open);
    }
  }, [handleOpenChange, newDeploymentOpen, open]);

  const providersQuery = useGetDeploymentProviders({
    refetchOnWindowFocus: false,
  });
  const providers = providersQuery.data?.deployment_providers || [];
  const providerId = providers[0]?.id ?? "";

  const {
    data: historyResponse,
    isLoading: isHistoryLoading,
    isError: isHistoryError,
  } = useGetFlowHistory({ flowId }, { enabled: newDeploymentOpen });

  const history = historyResponse?.entries ?? [];

  const checkpointGroups = useMemo(() => {
    const checkpoints = [
      {
        id: CURRENT_DRAFT_ID,
        name: "Current Draft",
        updatedDate: "Editor state (snapshot created on deploy)",
      },
      ...history.map((entry: FlowHistoryEntry) => ({
        id: entry.id,
        name: entry.version_tag ? `Version ${entry.version_tag}` : "Checkpoint",
        updatedDate: new Date(entry.created_at).toLocaleString(),
      })),
    ];
    return [{ flowId, flowName, checkpoints }];
  }, [flowId, flowName, history]);

  useEffect(() => {
    if (!newDeploymentOpen) {
      prevSelectedKeyRef.current = "";
      setDetectedEnvVars([]);
      return;
    }

    if (!deploymentName.trim()) {
      setDeploymentName(flowName);
    }

    if (selectedItems.size === 0) {
      const initialId =
        previewId && previewId !== CURRENT_DRAFT_ID
          ? previewId
          : (history[0]?.id ?? CURRENT_DRAFT_ID);
      setSelectedItems(new Set([initialId]));
    }
  }, [
    deploymentName,
    flowName,
    history,
    newDeploymentOpen,
    previewId,
    selectedItems.size,
    setDeploymentName,
    setSelectedItems,
  ]);

  const { mutateAsync: detectDeploymentEnvVars } =
    usePostDetectDeploymentEnvVars();
  useEffect(() => {
    if (!newDeploymentOpen) return;
    const selectedCheckpointIds = Array.from(selectedItems).filter(
      (id) => id !== CURRENT_DRAFT_ID,
    );
    if (selectedCheckpointIds.length === 0) {
      setDetectedEnvVars([]);
      return;
    }
    let cancelled = false;
    const detect = async () => {
      try {
        const response = await detectDeploymentEnvVars({
          reference_ids: selectedCheckpointIds,
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
  }, [detectDeploymentEnvVars, newDeploymentOpen, selectedItems]);

  const { mutateAsync: createSnapshot } = usePostCreateSnapshot();
  const createDeploymentMutation = usePostCreateDeployment();

  const selectedReviewItems = useMemo(() => {
    const checkpointNameMap = new Map(
      checkpointGroups[0]?.checkpoints.map((item) => [item.id, item.name]),
    );
    return Array.from(selectedItems).map((id) => ({
      name: `${flowName} (${checkpointNameMap.get(id) || "Checkpoint"})`,
    }));
  }, [checkpointGroups, flowName, selectedItems]);

  const handleCreateDeployment = async () => {
    if (!providerId) {
      setErrorData({
        title: "No deployment provider found",
        list: ["Register a provider first to deploy from the flow editor."],
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

    const selectedCheckpointIds = Array.from(selectedItems).filter(Boolean);
    if (selectedCheckpointIds.length === 0) {
      setErrorData({ title: "Select at least one checkpoint to deploy." });
      return;
    }

    let resolvedCheckpointIds = selectedCheckpointIds.filter(
      (id) => id !== CURRENT_DRAFT_ID,
    );

    if (selectedCheckpointIds.includes(CURRENT_DRAFT_ID)) {
      const createdSnapshot = await createSnapshot({
        flowId,
        description: "Snapshot created from Flow Editor deploy action",
      });
      resolvedCheckpointIds = [createdSnapshot.id, ...resolvedCheckpointIds];
    }

    const payload: DeploymentCreatePayload = {
      provider_id: providerId,
      spec: {
        name: deploymentName.trim(),
        description: deploymentDescription.trim(),
        type: deploymentType === "MCP" ? "mcp" : "agent",
      },
      flow_versions: { ids: resolvedCheckpointIds },
    };

    const environmentVariables = envVars.reduce<
      Record<string, { source: "raw" | "variable"; value: string }>
    >((acc, item) => {
      const key = item.key.trim();
      const value = item.value.trim();
      if (!key || !value) return acc;
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
          name: deploymentName.trim(),
          description: deploymentDescription.trim(),
          environment_variables: environmentVariables,
        },
      };
    }

    try {
      await createDeploymentMutation.mutateAsync(payload);
      setSuccessData({ title: "Deployment created" });
      handleSubmit();
      onOpenChange(false);
    } catch {
      setErrorData({
        title: "Could not create deployment",
        list: ["Please verify provider configuration and deployment payload."],
      });
    }
  };

  return (
    <>
      <StepperModal
        open={newDeploymentOpen}
        onOpenChange={(nextOpen) => {
          handleOpenChange(nextOpen);
          onOpenChange(nextOpen);
        }}
        currentStep={currentStep}
        totalSteps={TOTAL_STEPS}
        title="Create Deployment"
        icon="Rocket"
        description="Deploy this flow directly from the editor"
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
                const selKey = Array.from(selectedItems).sort().join(",");
                const selectionChanged = selKey !== prevSelectedKeyRef.current;
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
            onSubmit={() => void handleCreateDeployment()}
            nextDisabled={
              (currentStep === 1 && !deploymentName.trim()) ||
              (currentStep === 2 && selectedItems.size === 0) ||
              (currentStep === 3 && validateEnvVars(envVars).length > 0)
            }
            isSubmitting={createDeploymentMutation.isPending}
            submitLabel="Deploy"
          />
        }
      >
        {providers.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border bg-muted/20 px-4 text-center">
            <p className="text-sm text-muted-foreground">
              No deployment provider is registered yet.
            </p>
            <Button onClick={() => setRegisterProviderOpen(true)}>
              Register Deployment Provider
            </Button>
          </div>
        ) : (
          <>
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
          </>
        )}
      </StepperModal>
      <RegisterDeploymentProviderModal
        open={registerProviderOpen}
        onOpenChange={setRegisterProviderOpen}
      />
      {isHistoryError && newDeploymentOpen && (
        <div className="sr-only">
          {isHistoryLoading ? "Loading history" : "History unavailable"}
        </div>
      )}
    </>
  );
}
