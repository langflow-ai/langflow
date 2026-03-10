type DeployFlowStepperProps = {
  currentStep: number;
  labels: string[];
};

export function DeployFlowStepper({
  currentStep,
  labels,
}: DeployFlowStepperProps) {
  return (
    <div className="absolute left-1/2 top-[-128px] -translate-x-1/2 flex flex-col items-center gap-4">
      <div className="text-2xl font-semibold pb-2">Deploy Flow</div>
      <div className="relative" style={{ width: 700, height: 52 }}>
        {/* Background track */}
        <div className="absolute top-4 left-0 right-0 h-[2px] bg-muted" />
        {/* Progress fill */}
        <div
          className="absolute top-4 left-0 h-[2px] bg-foreground transition-all duration-300"
          style={{
            width: `${((currentStep - 1) / (labels.length - 1)) * 100}%`,
          }}
        />
        {labels.map((label, i) => {
          const stepNum = i + 1;
          const isActive = stepNum === currentStep;
          const isCompleted = stepNum < currentStep;
          const pct = (i / (labels.length - 1)) * 100;
          return (
            <div
              key={label}
              className="absolute z-10 flex flex-col items-center gap-1 -translate-x-1/2"
              style={{ left: `${pct}%` }}
            >
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-foreground text-background"
                    : isCompleted
                      ? "bg-foreground text-background"
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {stepNum}
              </div>
              <span
                className={`text-xs whitespace-nowrap ${
                  isActive || isCompleted
                    ? "text-foreground"
                    : "text-muted-foreground"
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
