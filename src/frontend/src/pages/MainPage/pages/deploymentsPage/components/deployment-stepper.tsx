import { useTranslation } from "react-i18next";
import { cn } from "@/utils/utils";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";

const STEP_LABEL_KEYS: Record<string, string> = {
  Provider: "deployments.provider",
  Type: "deployments.labelType",
  Flows: "deployments.stepFlows",
  Review: "deployments.review",
  Deployed: "deployments.deployed",
};

export const CREATE_STEPS = [
  { number: 1, label: "Provider" },
  { number: 2, label: "Type" },
  { number: 3, label: "Flows" },
  { number: 4, label: "Review" },
] as const;

export const CREATE_DEPLOYED_STEPS = [
  { number: 1, label: "Provider" },
  { number: 2, label: "Type" },
  { number: 3, label: "Flows" },
  { number: 4, label: "Deployed" },
] as const;

const EDIT_STEPS = [
  { number: 1, label: "Type" },
  { number: 2, label: "Flows" },
  { number: 3, label: "Review" },
] as const;

export const DEPLOYMENT_STEPS = CREATE_STEPS;

interface DeploymentStepperProps {
  steps?: readonly { number: number; label: string }[];
  currentStepOverride?: number;
}

export default function DeploymentStepper({
  steps: stepsProp,
  currentStepOverride,
}: DeploymentStepperProps) {
  const { t } = useTranslation();
  const { currentStep, isEditMode } = useDeploymentStepper();
  const steps = stepsProp ?? (isEditMode ? EDIT_STEPS : CREATE_STEPS);
  const activeStep = currentStepOverride ?? currentStep;
  const progressPercent = ((activeStep - 1) / (steps.length - 1)) * 100;

  return (
    <div className="relative mx-auto h-[52px] w-full max-w-[700px]">
      <div className="absolute left-4 right-4 top-4 h-[2px] bg-muted">
        <div
          className="h-full bg-foreground transition-all duration-300"
          style={{ width: `${progressPercent}%` }}
        />
      </div>
      <div className="relative flex h-full items-start justify-between">
        {steps.map((step) => (
          <div key={step.number} className="flex flex-col items-center gap-1">
            <div
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-colors",
                activeStep >= step.number
                  ? "bg-foreground text-background"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {step.number}
            </div>
            <span
              className={cn(
                "whitespace-nowrap text-xs text-foreground",
                activeStep >= step.number && "font-medium",
              )}
            >
              {t(STEP_LABEL_KEYS[step.label] ?? step.label)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
