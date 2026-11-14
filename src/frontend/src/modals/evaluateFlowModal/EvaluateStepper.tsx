import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

export interface EvaluateStep {
  key: string;
  label: string;
}

interface EvaluateStepperProps {
  steps: readonly EvaluateStep[];
  current: number;
  /** Going back to a finished step; later steps open with Next, once the current one is valid. */
  onSelect: (index: number) => void;
}

/** Where the user is in the Evaluate dialog; finished steps can be reopened. */
export default function EvaluateStepper({
  steps,
  current,
  onSelect,
}: EvaluateStepperProps) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("evals.evaluate.stepsLabel")}>
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-2">
        {steps.map((step, index) => {
          const done = index < current;
          const active = index === current;
          const marker = (
            <span
              aria-hidden="true"
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular-nums",
                active && "border-foreground bg-foreground text-background",
                done && "border-foreground text-foreground",
                !active && !done && "text-muted-foreground",
              )}
            >
              {done ? (
                <ForwardedIconComponent name="Check" className="h-3.5 w-3.5" />
              ) : (
                index + 1
              )}
            </span>
          );
          const label = (
            <span
              className={cn(
                "text-sm",
                active ? "font-medium" : "text-muted-foreground",
              )}
            >
              {step.label}
            </span>
          );
          return (
            <li key={step.key} className="flex items-center gap-2">
              {done ? (
                <button
                  type="button"
                  onClick={() => onSelect(index)}
                  className="flex items-center gap-2 rounded-md px-1 py-0.5 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  data-testid={`evaluate-step-${step.key}`}
                >
                  {marker}
                  {label}
                  <span className="sr-only">
                    {t("evals.evaluate.stepDone")}
                  </span>
                </button>
              ) : (
                <span
                  className="flex items-center gap-2 px-1 py-0.5"
                  aria-current={active ? "step" : undefined}
                  data-testid={`evaluate-step-${step.key}`}
                >
                  {marker}
                  {label}
                </span>
              )}
              {index < steps.length - 1 && (
                <span aria-hidden="true" className="h-px w-6 bg-border" />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
