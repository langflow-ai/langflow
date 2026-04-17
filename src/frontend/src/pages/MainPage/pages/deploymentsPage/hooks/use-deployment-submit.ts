import { useState } from "react";
import { usePostProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account";
import { usePatchDeployment } from "@/controllers/API/queries/deployments/use-patch-deployment";
import { usePostDeployment } from "@/controllers/API/queries/deployments/use-post-deployment";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import { useErrorAlert } from "./use-error-alert";

type DeploymentPhase = "idle" | "deploying" | "deployed";

interface UseDeploymentSubmitParams {
  setOpen: (open: boolean) => void;
  onTestDeployment?: (
    deployment: { id: string; name: string },
    providerId: string,
  ) => void;
  onDeployingChange: (isDeploying: boolean) => void;
}

export function useDeploymentSubmit({
  setOpen,
  onTestDeployment,
  onDeployingChange,
}: UseDeploymentSubmitParams) {
  const [deploymentPhase, setDeploymentPhase] =
    useState<DeploymentPhase>("idle");
  const [createdDeployment, setCreatedDeployment] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [isCreatingAccount, setIsCreatingAccount] = useState(false);

  const {
    isEditMode,
    currentStep,
    totalSteps,
    handleNext,
    selectedInstance,
    setSelectedInstance,
    needsProviderAccountCreation,
    buildProviderAccountPayload,
    buildDeploymentPayload,
    buildDeploymentUpdatePayload,
  } = useDeploymentStepper();

  const showError = useErrorAlert();

  const { mutateAsync: createProviderAccount } = usePostProviderAccount();
  const { mutateAsync: createDeployment } = usePostDeployment();
  const { mutateAsync: updateDeployment } = usePatchDeployment();

  const isDeploying = deploymentPhase === "deploying";
  const isDeployed = deploymentPhase === "deployed";
  const isInDeployPhase = isDeploying || isDeployed;

  const isProviderStep = !isEditMode && currentStep === 1;
  const isFinalStep = currentStep === totalSteps;

  const handleStepNext = async () => {
    if (isProviderStep && needsProviderAccountCreation) {
      const accountPayload = buildProviderAccountPayload();
      if (!accountPayload) {
        return;
      }
      try {
        setIsCreatingAccount(true);
        const newAccount = await createProviderAccount(accountPayload);
        setSelectedInstance(newAccount);
      } catch (err: unknown) {
        showError("Failed to create provider account", err);
        return;
      } finally {
        setIsCreatingAccount(false);
      }
    }

    handleNext();
  };

  const handleDeploy = async () => {
    try {
      setDeploymentPhase("deploying");
      onDeployingChange(true);

      if (isEditMode) {
        const payload = buildDeploymentUpdatePayload();
        await updateDeployment(payload);
        onDeployingChange(false);
        setOpen(false);
        return;
      }

      const providerId = selectedInstance?.id;
      if (!providerId) {
        setDeploymentPhase("idle");
        return;
      }

      const payload = buildDeploymentPayload(providerId);
      const result = await createDeployment(payload);
      if (
        result &&
        typeof result === "object" &&
        "id" in result &&
        "name" in result
      ) {
        setCreatedDeployment({
          id: String(result.id),
          name: String(result.name),
        });
      }
      setDeploymentPhase("deployed");
      onDeployingChange(false);
    } catch (err: unknown) {
      setDeploymentPhase("idle");
      onDeployingChange(false);
      const action = isEditMode ? "update" : "create";
      showError(`Failed to ${action} deployment`, err);
    }
  };

  const handleTest = () => {
    if (!createdDeployment || !selectedInstance?.id) {
      return;
    }

    onTestDeployment?.(createdDeployment, selectedInstance.id);
    setOpen(false);
  };

  return {
    deploymentPhase,
    createdDeployment,
    isCreatingAccount,
    isDeploying,
    isDeployed,
    isInDeployPhase,
    isFinalStep,
    handleStepNext,
    handleDeploy,
    handleTest,
  };
}
