import { useMemo } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

const LOADING_VARIANTS = [
  "Processing...",
  "Thinking...",
  "Analyzing...",
  "Working...",
  "Computing...",
  "Calculating...",
  "Pondering...",
  "Figuring out...",
  "Running...",
  "Crunching...",
];

export const LoadingIndicator = () => {
  const loadingText = useMemo(
    () => LOADING_VARIANTS[Math.floor(Math.random() * LOADING_VARIANTS.length)],
    [],
  );

  return (
    <div className="flex items-center gap-2 py-1 font-mono text-sm text-muted-foreground">
      <ForwardedIconComponent
        name="Loader2"
        className="h-3.5 w-3.5 animate-spin"
      />
      <span>{loadingText}</span>
    </div>
  );
};
