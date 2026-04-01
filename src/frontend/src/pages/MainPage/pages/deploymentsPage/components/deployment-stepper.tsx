import { cn } from "@/utils/utils";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";

export const DEPLOYMENT_STEPS = [
  { number: 1, label: "Provider" },
  { number: 2, label: "Type" },
  { number: 3, label: "Attach Flows" },
  { number: 4, label: "Review" },
] as const;

export default function DeploymentStepper() {
  const { currentStep } = useDeploymentStepper();
  const progressPercent =
    ((currentStep - 1) / (DEPLOYMENT_STEPS.length - 1)) * 100;

  return (
    <div className="relative mx-auto h-[52px] w-full max-w-[700px]">
      {/* Track container — inset by half the circle width (16px) */}
      <div className="absolute left-4 right-4 top-4 h-[2px] bg-muted">
        {/* Progress fill */}
        <div
          className="h-full bg-foreground transition-all duration-300"
          style={{ width: `${progressPercent}%` }}
        />
      </div>
      {/* Step indicators */}
      <div className="relative flex h-full items-start justify-between">
        {DEPLOYMENT_STEPS.map((step) => (
          <div key={step.number} className="flex flex-col items-center gap-1">
            <div
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-colors",
                currentStep >= step.number
                  ? "bg-foreground text-background"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {step.number}
            </div>
            <span className="whitespace-nowrap text-xs text-muted-foreground">
              {step.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
