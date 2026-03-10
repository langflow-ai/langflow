import { cn } from "@/utils/utils";

interface HorizontalStepRailProps {
  stepLabels: string[];
  currentStep: number;
}

export function HorizontalStepRail({
  stepLabels,
  currentStep,
}: HorizontalStepRailProps) {
  return (
    <nav className="flex w-full items-center pb-6">
      {stepLabels.map((label, index) => {
        const stepNumber = index + 1;
        const isCompleted = stepNumber < currentStep;
        const isCurrent = stepNumber === currentStep;

        return (
          <div key={label} className="contents">
            {/* Connector line before circle (skip for first) */}
            {index > 0 && (
              <div
                className={cn(
                  "h-0.5 flex-1 transition-colors duration-300",
                  isCompleted || isCurrent
                    ? "bg-primary"
                    : "bg-muted-foreground/20",
                )}
              />
            )}

            {/* Step circle + label anchored below */}
            <div className="relative shrink-0">
              <div
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-colors duration-300",
                  isCompleted || isCurrent
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground",
                )}
              >
                {stepNumber}
              </div>
              <span
                className={cn(
                  "absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs transition-colors duration-300",
                  isCurrent
                    ? "font-semibold text-foreground"
                    : isCompleted
                      ? "text-foreground"
                      : "text-muted-foreground",
                )}
              >
                {label}
              </span>
            </div>
          </div>
        );
      })}
    </nav>
  );
}
