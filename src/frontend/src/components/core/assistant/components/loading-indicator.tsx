import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import type { ProgressInfo } from "../assistant.types";
import { getStepConfig } from "../helpers/step-config";

type LoadingIndicatorProps = {
  progress?: ProgressInfo;
};

export const LoadingIndicator = ({ progress }: LoadingIndicatorProps) => {
  if (!progress) {
    return (
      <div className="flex items-center gap-2 py-2 font-mono text-sm text-muted-foreground">
        <ForwardedIconComponent
          name="Loader2"
          className="h-3.5 w-3.5 animate-spin"
        />
        <span>Generating...</span>
      </div>
    );
  }

  const { step, attempt, maxAttempts, error } = progress;
  const config = getStepConfig(step, attempt, maxAttempts, error);

  return (
    <div className={cn("flex items-center gap-2 py-2 font-mono text-sm", config.color)}>
      <ForwardedIconComponent
        name={config.icon}
        className={cn("h-3.5 w-3.5", config.spin && "animate-spin")}
      />
      <span>{config.text}</span>
    </div>
  );
};
