/**
 * Step configuration helper for progress indicator.
 * Maps progress step types to their visual configuration (icon, color, text).
 */

import type { ProgressStep } from "../assistant.types";

export type StepConfig = {
  icon: string;
  text: string;
  color: string;
  spin?: boolean;
};

export const getStepConfig = (
  step: ProgressStep,
  attempt: number,
  maxAttempts: number,
  error?: string,
): StepConfig => {
  switch (step) {
    case "generating":
      return {
        icon: "Sparkles",
        text: "Generating code...",
        color: "text-muted-foreground",
        spin: false,
      };
    case "generation_complete":
      return {
        icon: "Check",
        text: "Code generation complete",
        color: "text-accent-emerald-foreground",
        spin: false,
      };
    case "extracting_code":
      // Skip this step in UI - no longer shown
      return {
        icon: "FileCode",
        text: "",
        color: "text-muted-foreground",
        spin: false,
      };
    case "validating":
      return {
        icon: "Shield",
        text: "Validating component code...",
        color: "text-muted-foreground",
        spin: true,
      };
    case "validated":
      return {
        icon: "CheckCircle",
        text: "Component validated!",
        color: "text-accent-emerald-foreground",
        spin: false,
      };
    case "validation_failed":
      return {
        icon: "XCircle",
        text: error ? `Validation failed: ${error}` : "Validation failed",
        color: "text-destructive",
        spin: false,
      };
    case "retrying":
      // attempt = current attempt that failed (1-indexed)
      // maxAttempts = total attempts (original + retries)
      // So retry number = attempt, max retries = maxAttempts - 1
      return {
        icon: "RefreshCw",
        text: `Retrying... (${attempt}/${maxAttempts - 1})`,
        color: "text-muted-foreground",
        spin: true,
      };
    default:
      return {
        icon: "Loader2",
        text: "Processing...",
        color: "text-muted-foreground",
        spin: true,
      };
  }
};
