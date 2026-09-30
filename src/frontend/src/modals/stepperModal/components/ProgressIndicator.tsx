import { MIN_PROGRESS_PERCENTAGE } from "../constants";

interface ProgressIndicatorProps {
  currentStep: number;
  totalSteps: number;
}

export function ProgressIndicator({
  currentStep,
  totalSteps,
}: ProgressIndicatorProps) {
  const progressPercentage = ((currentStep - 1) / (totalSteps - 1)) * 100;

  return (
    <div className="flex items-center gap-3">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{
            width: `${Math.max(progressPercentage, MIN_PROGRESS_PERCENTAGE)}%`,
          }}
        />
      </div>
      <span className="text-sm text-muted-foreground whitespace-nowrap">
        {currentStep}/{totalSteps} completed
      </span>
    </div>
  );
}
