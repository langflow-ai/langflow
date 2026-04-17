import { useCallback, useMemo, useState } from "react";
import type { DeploymentProvider, ProviderAccount } from "../types";

interface UseDeploymentStepperNavigationParams {
  isEditMode: boolean;
  initialStep?: number;
  selectedProvider: DeploymentProvider | null;
  selectedInstance: ProviderAccount | null;
  hasValidCredentials: boolean;
  deploymentName: string;
  selectedLlm: string;
  attachedFlowCount: number;
  hasToolNameErrors: boolean;
}

export function useDeploymentStepperNavigation({
  isEditMode,
  initialStep,
  selectedProvider,
  selectedInstance,
  hasValidCredentials,
  deploymentName,
  selectedLlm,
  attachedFlowCount,
  hasToolNameErrors,
}: UseDeploymentStepperNavigationParams) {
  const totalSteps = isEditMode ? 3 : 4;
  const minStep = initialStep ?? 1;
  const [currentStep, setCurrentStep] = useState(minStep);

  const getLogicalStep = useCallback(
    (step: number) => (isEditMode ? step + 1 : step),
    [isEditMode],
  );

  const canGoNext = useMemo(() => {
    const logicalStep = getLogicalStep(currentStep);

    if (logicalStep === 1) {
      return (
        selectedProvider !== null &&
        (selectedInstance !== null || hasValidCredentials)
      );
    }

    if (logicalStep === 2) {
      return deploymentName.trim() !== "" && selectedLlm.trim() !== "";
    }

    if (logicalStep === 3) {
      return isEditMode || attachedFlowCount > 0;
    }

    if (logicalStep === 4) {
      return !hasToolNameErrors;
    }

    return true;
  }, [
    attachedFlowCount,
    currentStep,
    deploymentName,
    getLogicalStep,
    hasToolNameErrors,
    hasValidCredentials,
    isEditMode,
    selectedInstance,
    selectedLlm,
    selectedProvider,
  ]);

  const handleNext = useCallback(() => {
    setCurrentStep((prev) => (prev < totalSteps ? prev + 1 : prev));
  }, [totalSteps]);

  const handleBack = useCallback(() => {
    setCurrentStep((prev) => (prev > minStep ? prev - 1 : prev));
  }, [minStep]);

  return {
    currentStep,
    totalSteps,
    minStep,
    canGoNext,
    handleNext,
    handleBack,
  };
}
