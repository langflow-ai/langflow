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

// Text variations for dynamic UI feedback
const GENERATING_VARIANTS = [
  "Generating code...",
  "Writing code...",
  "Crafting code...",
  "Building code...",
  "Creating code...",
  "Composing code...",
  "Coding away...",
  "Conjuring code...",
  "Assembling code...",
  "Forging code...",
];

const VALIDATING_VARIANTS = [
  "Validating component code...",
  "Checking component code...",
  "Verifying component code...",
  "Testing component code...",
  "Analyzing component code...",
  "Inspecting component code...",
  "Reviewing component code...",
  "Evaluating component code...",
  "Examining component code...",
  "Scanning component code...",
];

const PROCESSING_VARIANTS = [
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

const getRandomVariant = (variants: string[]): string =>
  variants[Math.floor(Math.random() * variants.length)];

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
        text: getRandomVariant(GENERATING_VARIANTS),
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
        text: getRandomVariant(VALIDATING_VARIANTS),
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
        text: getRandomVariant(PROCESSING_VARIANTS),
        color: "text-muted-foreground",
        spin: true,
      };
  }
};
