import ForwardedIconComponent from "@/components/common/genericIconComponent";

interface StepRailProps {
  icon: string;
  title: string;
  description?: string;
  stepLabels: string[];
  currentStep: number;
}

export function StepRail({
  icon,
  title,
  description,
  stepLabels,
  currentStep,
}: StepRailProps) {
  return (
    <div className="flex w-[200px] shrink-0 flex-col gap-6 rounded-l-xl bg-muted/30 px-5 py-6">
      <div className="flex flex-col gap-1.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
          <ForwardedIconComponent name={icon} className="h-4 w-4" />
        </div>
        <h2 className="mt-1 text-sm font-semibold">{title}</h2>
        {description && (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {description}
          </p>
        )}
      </div>

      <nav className="flex flex-col gap-0.5">
        {stepLabels.map((label, index) => {
          const stepNumber = index + 1;
          const isCompleted = stepNumber < currentStep;
          const isCurrent = stepNumber === currentStep;

          return (
            <div key={label} className="flex items-stretch gap-3">
              <div className="flex flex-col items-center">
                {isCompleted ? (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary">
                    <ForwardedIconComponent
                      name="Check"
                      className="h-3.5 w-3.5 text-background"
                    />
                  </div>
                ) : isCurrent ? (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-primary">
                    <div className="h-2 w-2 rounded-full bg-primary" />
                  </div>
                ) : (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-muted-foreground/30" />
                )}
                {index < stepLabels.length - 1 && (
                  <div
                    className={`my-0.5 w-0.5 flex-1 rounded-full ${
                      isCompleted ? "bg-primary" : "bg-muted-foreground/20"
                    }`}
                  />
                )}
              </div>
              <span
                className={`pb-4 pt-0.5 text-sm ${
                  isCurrent
                    ? "font-semibold text-foreground"
                    : isCompleted
                      ? "text-foreground"
                      : "text-muted-foreground"
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </nav>
    </div>
  );
}
