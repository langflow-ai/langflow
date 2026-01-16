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
        text: `Generating code... (${attempt}/${maxAttempts})`,
        color: "text-blue-500",
        spin: false,
      };
    case "generation_complete":
      return {
        icon: "Check",
        text: "Code generation complete",
        color: "text-green-500",
        spin: false,
      };
    case "extracting_code":
      return {
        icon: "FileCode",
        text: "Extracting Python code...",
        color: "text-purple-500",
        spin: false,
      };
    case "validating":
      return {
        icon: "Shield",
        text: "Validating component...",
        color: "text-yellow-500",
        spin: true,
      };
    case "validated":
      return {
        icon: "CheckCircle",
        text: "Component validated!",
        color: "text-green-500",
        spin: false,
      };
    case "validation_failed":
      return {
        icon: "XCircle",
        text: error ? `Validation failed: ${error.slice(0, 50)}...` : "Validation failed",
        color: "text-red-500",
        spin: false,
      };
    case "retrying":
      return {
        icon: "RefreshCw",
        text: `Retrying... (${attempt + 1}/${maxAttempts})`,
        color: "text-orange-500",
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
