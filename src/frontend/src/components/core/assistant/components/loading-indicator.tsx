import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { ProgressInfo } from "../assistant.types";

type LoadingIndicatorProps = {
  progress?: ProgressInfo;
};

export const LoadingIndicator = ({ progress }: LoadingIndicatorProps) => {
  const getStatusText = (): string => {
    if (!progress) return "Generating...";
    const { step, attempt, maxAttempts } = progress;
    if (step === "generating") {
      return "Generating...";
    }
    return `Validating... attempt ${attempt}/${maxAttempts}`;
  };

  return (
    <div className="flex items-center gap-2 py-2 font-mono text-sm text-muted-foreground">
      <ForwardedIconComponent
        name="Loader2"
        className="h-3.5 w-3.5 animate-spin"
      />
      <span>{getStatusText()}</span>
    </div>
  );
};
