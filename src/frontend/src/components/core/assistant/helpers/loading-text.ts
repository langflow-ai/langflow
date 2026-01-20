import { LOADING_VARIANTS, VALIDATING_VARIANTS } from "../assistant.constants";
import type { ProgressInfo } from "../assistant.types";

const getRandomVariant = (variants: string[]): string => {
  return variants[Math.floor(Math.random() * variants.length)];
};

export const getLoadingText = (progress?: ProgressInfo): string => {
  const isValidating = progress?.step === "validating";
  const isRetrying = progress?.step === "retrying";

  if (isRetrying && progress) {
    const maxRetries = (progress.maxAttempts ?? 1) - 1;
    return `Retrying... (${progress.attempt}/${maxRetries})`;
  }

  const variants = isValidating ? VALIDATING_VARIANTS : LOADING_VARIANTS;
  return getRandomVariant(variants);
};
