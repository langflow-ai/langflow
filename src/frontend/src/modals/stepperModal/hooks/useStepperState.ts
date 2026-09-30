import { useCallback, useMemo, useState } from "react";
import type {
  StepperState,
  StepperStepConfig,
  UseStepperStateOptions,
} from "../types";

function clampStep(step: number, minStep: number, totalSteps: number): number {
  if (totalSteps === 0) return 0;
  return Math.min(Math.max(step, minStep), totalSteps);
}

function resolveCanNext(step: StepperStepConfig | undefined): boolean {
  if (!step || step.canNext === undefined) return true;
  return typeof step.canNext === "function" ? step.canNext() : step.canNext;
}

/**
 * Headless stepper transition logic: 1-based step index, next/back/goTo with
 * clamping, per-step validation gate, back floor (minStep), busy gating and
 * progress. Holds NO step content or domain state — consumers keep their own
 * form/domain state and derive `steps` (conditional steps = a computed list;
 * when the list shrinks below the current step, the exposed step clamps to
 * the last one without losing the underlying position).
 */
export function useStepperState({
  steps,
  initialStep = 1,
  minStep = 1,
  isBusy = false,
  onStepChange,
}: UseStepperStateOptions): StepperState {
  const totalSteps = steps.length;
  const [rawStep, setRawStep] = useState(() =>
    clampStep(initialStep, minStep, totalSteps),
  );

  const currentStep = clampStep(rawStep, minStep, totalSteps);
  const currentStepIndex = currentStep - 1;
  const currentStepConfig = steps[currentStepIndex];

  const commitStep = useCallback(
    (from: number, to: number) => {
      if (to === from) return;
      setRawStep(to);
      onStepChange?.(from, to);
    },
    [onStepChange],
  );

  const canGoNext =
    !isBusy && currentStep < totalSteps && resolveCanNext(currentStepConfig);
  const canGoBack = !isBusy && currentStep > minStep;

  const next = useCallback(() => {
    if (!canGoNext) return;
    commitStep(currentStep, currentStep + 1);
  }, [canGoNext, currentStep, commitStep]);

  const back = useCallback(() => {
    if (!canGoBack) return;
    commitStep(currentStep, currentStep - 1);
  }, [canGoBack, currentStep, commitStep]);

  const goTo = useCallback(
    (stepIdOrNumber: string | number) => {
      if (isBusy) return;
      const target =
        typeof stepIdOrNumber === "number"
          ? stepIdOrNumber
          : steps.findIndex((step) => step.id === stepIdOrNumber) + 1;
      if (target < 1) return;
      commitStep(currentStep, clampStep(target, minStep, totalSteps));
    },
    [isBusy, steps, currentStep, minStep, totalSteps, commitStep],
  );

  const reset = useCallback(() => {
    setRawStep(clampStep(initialStep, minStep, totalSteps));
  }, [initialStep, minStep, totalSteps]);

  const progressPercent =
    totalSteps <= 1 ? 100 : ((currentStep - 1) / (totalSteps - 1)) * 100;

  return useMemo(
    () => ({
      currentStep,
      currentStepIndex,
      currentStepId: currentStepConfig?.id ?? "",
      totalSteps,
      minStep,
      isFirstStep: currentStep <= minStep,
      isLastStep: currentStep === totalSteps,
      canGoNext,
      canGoBack,
      isBusy,
      progressPercent,
      next,
      back,
      goTo,
      reset,
    }),
    [
      currentStep,
      currentStepIndex,
      currentStepConfig?.id,
      totalSteps,
      minStep,
      canGoNext,
      canGoBack,
      isBusy,
      progressPercent,
      next,
      back,
      goTo,
      reset,
    ],
  );
}
